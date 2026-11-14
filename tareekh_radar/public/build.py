"""Build the static JSON data behind the public Case Clock site.

Input : one or more DDL extracts (cases.parquet from `ddl-extract`, any number of filing years).
Output: site/data/{meta.json, national.json, states/<code>.json, districts/<id>.json, category_mapping.json}

Only aggregates are written - never individual case records - and any group with fewer
than `min_n` cases is suppressed. Everything is recomputed from the source files.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from ..categories import CATEGORIES, assign_categories, type_key
from ..cleaning import clean_cases
from .stats import OUTCOME_GROUPS, group_stats, outcome_group

log = logging.getLogger(__name__)

COLUMNS = ["case_id", "court_id", "case_type", "filing_date", "disposal_date", "case_status", "first_listing_date",
           "last_listing_date", "next_listing_date", "disposal_nature", "case_category", "state_code", "state_name",
           "district_id", "district_name", "filing_year", "current_purpose", "source_reference", "act", "section"]


def _clean_json(o):
    if isinstance(o, dict):
        return {str(k): _clean_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean_json(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    return o


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean_json(payload), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _snapshot(df: pd.DataFrame) -> pd.Timestamp:
    """Typical last update of the records: median last-listing date of pending cases.
    Display only - durations of pending cases use each case's own last listing date."""
    v = df.loc[df["case_status"] == "PENDING", "last_listing_date"].dropna()
    if v.empty:
        v = df["last_listing_date"].dropna()
    return pd.Timestamp(v.quantile(0.5)).normalize() if len(v) else pd.NaT


def _summary(df: pd.DataFrame, snapshot, min_n: int, max_month: int) -> dict:
    s = group_stats(df, snapshot, min_n, max_month)
    s.pop("curve_monthly_share_decided", None)
    by_year = {}
    for y, g in df.groupby("filing_year", observed=True):
        gs = group_stats(g, snapshot, min_n, 36)
        by_year[str(y)] = {"n": gs["n"], "share_undecided_at_3y": gs.get("share_undecided_at_3y"),
                           "median_days_to_decision": (gs.get("time_to_decision_days") or {}).get("p50")}
    s["by_filing_year"] = by_year
    mix = df["case_category"].value_counts(normalize=True).round(4)
    s["category_mix"] = {str(k): float(v) for k, v in mix.items() if v > 0}
    return s


SLIM = ["filing_date", "disposal_date", "case_status", "outcome_group", "first_listing_date", "last_listing_date",
        "next_listing_date", "case_category", "filing_year", "district_id", "district_name", "state_name"]
CAT_COLS = ["case_status", "outcome_group", "case_category", "filing_year", "district_id", "district_name", "state_name"]


class _NationalAcc:
    """Memory-light national accumulator (numpy arrays per category instead of full frames)."""

    def __init__(self):
        self.parts: dict[str, dict[str, list]] = {}

    def add(self, cat: str, g: pd.DataFrame) -> None:
        from .stats import durations_events

        a = self.parts.setdefault(cat, {"dur": [], "ev": [], "ttf": [], "gap": [], "out": {}, "n": 0,
                                        "n_pending": 0, "n_decided": 0, "n_moved": 0, "excl": 0})
        d, e, x = durations_events(g)
        a["dur"].append(d.astype(np.int32))
        a["ev"].append(e)
        a["excl"] += x
        ttf = (g["first_listing_date"] - g["filing_date"]).dt.days
        a["ttf"].append(ttf[ttf >= 0].to_numpy(dtype=np.int32))
        pend = g[g["case_status"] == "PENDING"]
        gap = (pend["next_listing_date"] - pend["last_listing_date"]).dt.days
        a["gap"].append(gap[gap >= 0].to_numpy(dtype=np.int32))
        moved = g["outcome_group"].eq("moved")
        a["n"] += len(g)
        a["n_pending"] += int((g["case_status"] == "PENDING").sum())
        a["n_decided"] += int(((g["case_status"] == "DISPOSED") & ~moved).sum())
        a["n_moved"] += int(moved.sum())
        disp = g[(g["case_status"] == "DISPOSED") & g["outcome_group"].notna() & ~moved]
        for k, v in disp["outcome_group"].value_counts().items():
            if v:
                a["out"][str(k)] = a["out"].get(str(k), 0) + int(v)

    def stats(self, min_n: int, max_month: int) -> dict:
        from .stats import kaplan_meier, km_curve, km_quantile

        res = {}
        for cat, a in self.parts.items():
            s = {"n": a["n"], "n_pending": a["n_pending"], "n_decided": a["n_decided"], "n_moved": a["n_moved"]}
            if a["n"] < min_n:
                res[cat] = {**s, "suppressed": True}
                continue
            times, surv = kaplan_meier(np.concatenate(a["dur"]), np.concatenate(a["ev"]))
            c = km_curve(times, surv, max_month)
            s.update(suppressed=False, n_excluded_bad_dates=a["excl"],
                     time_to_decision_days={"p50": km_quantile(times, surv, 0.5), "p75": km_quantile(times, surv, 0.75),
                                            "p90": km_quantile(times, surv, 0.9),
                                            "max_followup": float(times[-1]) if len(times) else None},
                     curve_monthly_share_decided=c,
                     share_undecided_at_3y=round(1 - c[36], 4) if c[36] is not None else None)
            n_out = sum(a["out"].values())
            s["n_outcomes"] = n_out
            if n_out >= min_n:
                s["outcomes"] = {k: round(v / n_out, 4) for k, v in sorted(a["out"].items(), key=lambda kv: -kv[1])}
            ttf = np.concatenate(a["ttf"])
            s["days_to_first_listing"] = ({"p50": float(np.percentile(ttf, 50)), "p90": float(np.percentile(ttf, 90))}
                                          if len(ttf) >= min_n else None)
            gap = np.concatenate(a["gap"])
            if len(gap) >= min_n:
                s["next_hearing_gap_days"] = {"n": int(len(gap)), **{f"p{q}": float(np.percentile(gap, q))
                                                                      for q in (50, 75, 90, 95)}}
                s["pending_next_gap_over_6m_share"] = round(float((gap > 182).mean()), 4)
            else:
                s["next_hearing_gap_days"] = None
                s["pending_next_gap_over_6m_share"] = None
            s["note"] = "Pooled across states; pending cases are censored at their own last listing date."
            res[cat] = s
        return res


def _load_state(files: list[Path], st: str, cfg: dict, mapping_counts: dict,
                min_filing_year: int | None = None) -> tuple[pd.DataFrame, int]:
    """Clean one file at a time for a state and keep only slim, categorical columns."""
    slims, unknown = [], 0
    for f in files:
        cols = [c for c in COLUMNS if c in pq.read_schema(f).names]
        raw = pd.read_parquet(f, columns=cols, filters=[("state_code", "==", st)])
        if raw.empty:
            continue
        # Re-derive categories with the current rules (so rule fixes don't need a re-extract).
        raw["case_category"] = assign_categories(raw["case_type"], raw.get("act"), raw.get("section")).to_numpy()
        cases, _rej, _dups, _q = clean_cases(raw, cfg)
        del raw
        cases["outcome_group"] = cases["disposal_nature"].map(
            {u: outcome_group(u) for u in pd.unique(cases["disposal_nature"].astype(object))})
        cases["case_category"] = cases["case_category"].fillna("other")
        unknown += int((cases["case_status"] == "UNKNOWN").sum())
        for k, n in cases.groupby([cases["case_type_raw"].map(type_key), "case_category"]).size().items():
            mapping_counts[k] = mapping_counts.get(k, 0) + int(n)
        if min_filing_year is not None:
            cases = cases[pd.to_numeric(cases["filing_year"], errors="coerce") >= min_filing_year]
        slim = cases[SLIM].copy()
        del cases
        for c in CAT_COLS:
            slim[c] = slim[c].astype("category")
        slims.append(slim)
    if not slims:
        return pd.DataFrame(), 0
    out = pd.concat(slims, ignore_index=True)
    for c in CAT_COLS:  # concat of differing categories falls back to object
        out[c] = out[c].astype("category")
    return out, unknown


def build_site_data(extract_paths: list[str | Path], out_dir: str | Path, cfg: dict, min_n: int = 30,
                    max_month: int = 132, min_filing_year: int | None = None) -> dict:
    """min_filing_year: drop earlier filing cohorts. Older DDL cohorts under-represent cases that were
    disposed quickly (case counts per filing year rise ~3x from 2010 to 2018), which biases durations upward."""
    out = Path(out_dir)
    files = [Path(p) for p in extract_paths]
    for f in files:
        if not f.exists():
            raise FileNotFoundError(f"Extract not found: {f} (run ddl-extract first)")
    states = sorted(set().union(*[set(pq.read_table(f, columns=["state_code"]).column(0).to_pylist()) for f in files]))
    nat = _NationalAcc()
    meta_states, mapping_counts = [], {}
    totals = {"cases": 0, "excluded_status_unknown": 0}
    years: set[str] = set()
    for st in states:
        cases, unknown = _load_state(files, st, cfg, mapping_counts, min_filing_year)
        if cases.empty:
            continue
        years.update(str(y) for y in cases["filing_year"].dropna().unique().tolist())
        snapshot = _snapshot(cases)
        totals["cases"] += len(cases)
        totals["excluded_status_unknown"] += unknown
        for cat, g in cases.groupby("case_category", observed=True):
            nat.add(str(cat), g)

        state_name = str(cases["state_name"].mode().iat[0])
        dist_meta, dist_summaries = [], []
        for did, g in cases.groupby("district_id", observed=True):
            did = str(did)
            dname = str(g["district_name"].mode().iat[0]) if g["district_name"].notna().any() else did
            cats = {str(cat): group_stats(cg, snapshot, min_n, max_month)
                    for cat, cg in g.groupby("case_category", observed=True)}
            summ = _summary(g, snapshot, min_n, max_month)
            _write(out / "districts" / f"{did}.json", {
                "id": did, "name": dname, "state_code": st, "state_name": state_name,
                "snapshot_date": str(snapshot.date()) if pd.notna(snapshot) else None, "summary": summ, "categories": cats})
            dist_meta.append({"id": did, "name": dname, "n": int(len(g)),
                              "categories": sorted(c for c, s in cats.items() if not s.get("suppressed"))})
            dist_summaries.append({"id": did, "name": dname, "n": int(len(g)),
                                   "median_days_to_decision": (summ.get("time_to_decision_days") or {}).get("p50"),
                                   "share_undecided_at_3y": summ.get("share_undecided_at_3y"),
                                   "pending_next_gap_over_6m_share": summ.get("pending_next_gap_over_6m_share")})
        state_cats = {str(cat): group_stats(cg, snapshot, min_n, max_month)
                      for cat, cg in cases.groupby("case_category", observed=True)}
        snap_s = str(snapshot.date()) if pd.notna(snapshot) else None
        _write(out / "states" / f"{st}.json", {
            "code": st, "name": state_name, "snapshot_date": snap_s,
            "summary": _summary(cases, snapshot, min_n, max_month), "categories": state_cats,
            "districts": sorted(dist_summaries, key=lambda d: d["name"])})
        meta_states.append({"code": st, "name": state_name, "n": int(len(cases)), "snapshot_date": snap_s,
                            "districts": sorted(dist_meta, key=lambda d: d["name"])})
        log.info("state %s %s: %d cases, %d districts", st, state_name, len(cases), len(dist_meta))
        del cases

    national = nat.stats(min_n, max_month)
    _write(out / "national.json", {"categories": national})
    top_map = sorted(mapping_counts.items(), key=lambda kv: -kv[1])[:1500]
    _write(out / "category_mapping.json", [{"type": k[0], "category": k[1], "cases": n} for k, n in top_map])
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Development Data Lab eCourts case data (Harvard Dataverse doi:10.7910/DVN/GHLGSW)",
        "source_url": "https://doi.org/10.7910/DVN/GHLGSW",
        "license": "Dataverse: CC0 1.0. DDL: CC BY-NC-SA 4.0 (non-commercial, attribution).",
        "citation": "Ash, Asher, Bhowmick, Bhupatiraju, Chen, Devi, Goessmann, Novosad, Siddiqi (2025), "
                    "In-Group Bias in the Indian Judiciary, Review of Economics and Statistics. doi:10.1162/rest_a_01569",
        "filing_years": sorted(years),
        "totals": {"cases": totals["cases"], "states": len(meta_states),
                   "districts": sum(len(s["districts"]) for s in meta_states),
                   "categories": len([c for c in national if c != "other"]),
                   "excluded_status_unknown": totals["excluded_status_unknown"]},
        "min_n": min_n,
        "min_filing_year": min_filing_year,
        "categories": CATEGORIES,
        "outcome_groups": OUTCOME_GROUPS,
        "example": None,
        "states": sorted(meta_states, key=lambda s: s["name"]),
    }
    _write(out / "meta.json", meta)
    meta["example"] = choose_example(out)
    build_purposes(files, out)
    build_rankings(out)
    return meta


def choose_example(out_dir: str | Path, categories=("cheque_bounce", "motor_accident", "matrimonial")) -> dict | None:
    """Pick the home-page example: the largest district group whose outcomes are mostly recorded
    (unspecified < 40%) and whose median time to decision is known. Writes it into meta.json."""
    out = Path(out_dir)
    best = None
    for p in (out / "districts").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for cat in categories:
            s = d["categories"].get(cat)
            if not s or s.get("suppressed") or not s.get("outcomes"):
                continue
            if s["outcomes"].get("unspecified", 0) >= 0.4 or (s.get("time_to_decision_days") or {}).get("p50") is None:
                continue
            if not s.get("next_hearing_gap_days"):
                continue
            score = (categories.index(cat), -s["n"])
            if best is None or score < best[0]:
                best = (score, {"district_id": d["id"], "district_name": d["name"], "state_name": d["state_name"],
                                "category": cat, "n": s["n"]})
    meta_path = out / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["example"] = best[1] if best else None
    _write(meta_path, meta)
    return meta["example"]


def normalize_purpose(text: str) -> str:
    """Same normalisation as site/js/help.js normPurpose: lowercase, keep a-z 0-9 and '/', collapse spaces."""
    import re

    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9/ ]+", " ", str(text).lower())).strip()


def build_purposes(extract_paths: list[str | Path], out_dir: str | Path, top: int = 400) -> dict:
    """Most common recorded hearing purposes ("stage") among pending cases, for the order-sheet decoder.

    Counts are real: the purpose recorded for each case still pending when DDL collected the data.
    """
    import duckdb

    files = [str(Path(p)) for p in extract_paths]
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    norm = ("trim(regexp_replace(regexp_replace(lower(current_purpose), '[^a-z0-9/ ]+', ' ', 'g'), "
            r"'\s+', ' ', 'g'))")
    base = f"FROM read_parquet({files!r}) WHERE disposal_date IS NULL AND current_purpose IS NOT NULL"
    total = con.execute(f"SELECT count(*) {base}").fetchone()[0]
    rows = con.execute(f"SELECT {norm} AS p, count(*) AS n {base} GROUP BY 1 HAVING p <> '' "
                       f"ORDER BY n DESC, p LIMIT {int(top)}").fetchall()
    payload = {"total_pending_with_purpose": int(total),
               "note": "Recorded purpose of the next listing for cases pending at data collection (normalised text).",
               "purposes": [{"text": p, "n": int(n)} for p, n in rows]}
    _write(Path(out_dir) / "purposes.json", payload)
    return payload


def build_rankings(out_dir: str | Path) -> dict:
    """Per case type, every district with enough cases sorted by median time to decision (fastest first).

    Rows are [district_id, median_days or None, n, share_undecided_at_3y]; None means the median was not reached
    within follow-up (slower than any reached value), so those rows sort last. Built from the published district JSON.
    """
    out = Path(out_dir)
    cats: dict[str, list] = {}
    for f in sorted((out / "districts").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for cat, s in (d.get("categories") or {}).items():
            if s.get("suppressed") or not s.get("time_to_decision_days"):
                continue
            p50 = s["time_to_decision_days"].get("p50")
            cats.setdefault(cat, []).append([d["id"], p50, s.get("n"), s.get("share_undecided_at_3y")])
    for rows in cats.values():
        rows.sort(key=lambda r: (r[1] is None, r[1] if r[1] is not None else 0, -(r[2] or 0)))
    payload = {"note": "Districts with at least min_n cases per type, fastest median first; null median = not reached in follow-up.",
               "categories": cats}
    _write(out / "rankings.json", payload)
    return payload
