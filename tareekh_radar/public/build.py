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
    for y, g in df.groupby("filing_year"):
        gs = group_stats(g, snapshot, min_n, 36)
        by_year[str(y)] = {"n": gs["n"], "share_undecided_at_3y": gs.get("share_undecided_at_3y"),
                           "median_days_to_decision": (gs.get("time_to_decision_days") or {}).get("p50")}
    s["by_filing_year"] = by_year
    s["category_mix"] = df["case_category"].value_counts(normalize=True).round(4).to_dict()
    return s


def build_site_data(extract_paths: list[str | Path], out_dir: str | Path, cfg: dict, min_n: int = 30,
                    max_month: int = 132) -> dict:
    out = Path(out_dir)
    files = [Path(p) for p in extract_paths]
    for f in files:
        if not f.exists():
            raise FileNotFoundError(f"Extract not found: {f} (run ddl-extract first)")
    states = sorted(set().union(*[set(pq.read_table(f, columns=["state_code"]).column(0).to_pylist()) for f in files]))
    national_parts: dict[str, list[pd.DataFrame]] = {}
    meta_states, mapping_counts = [], {}
    totals = {"cases": 0, "excluded_status_unknown": 0}
    years: set[str] = set()
    example = None
    for st in states:
        parts = [pd.read_parquet(f, columns=[c for c in COLUMNS if c in pq.read_schema(f).names],
                                 filters=[("state_code", "==", st)]) for f in files]
        raw = pd.concat([p for p in parts if len(p)], ignore_index=True)
        if raw.empty:
            continue
        # Re-derive categories with the current rules (so rule fixes don't need a re-extract).
        raw["case_category"] = assign_categories(raw["case_type"], raw.get("act"), raw.get("section")).to_numpy()
        cases, _rej, _dups, _q = clean_cases(raw, cfg)
        cases["outcome_group"] = cases["disposal_nature"].map(
            {u: outcome_group(u) for u in pd.unique(cases["disposal_nature"].astype(object))})
        cases["case_category"] = cases["case_category"].fillna("other")
        years.update(cases["filing_year"].dropna().unique().tolist())
        snapshot = _snapshot(cases)
        totals["cases"] += len(cases)
        totals["excluded_status_unknown"] += int((cases["case_status"] == "UNKNOWN").sum())
        for k, n in cases.groupby([cases["case_type_raw"].map(type_key), "case_category"]).size().items():
            mapping_counts[k] = mapping_counts.get(k, 0) + int(n)
        slim = cases[["filing_date", "disposal_date", "case_status", "outcome_group", "first_listing_date",
                      "last_listing_date", "next_listing_date", "case_category", "filing_year"]].copy()
        slim["snapshot"] = snapshot
        for cat, g in slim.groupby("case_category"):
            national_parts.setdefault(cat, []).append(g)

        state_name = cases["state_name"].mode().iat[0]
        dist_meta, dist_summaries = [], []
        for did, g in cases.groupby("district_id"):
            dname = g["district_name"].mode().iat[0] if g["district_name"].notna().any() else did
            cats = {cat: group_stats(cg, snapshot, min_n, max_month) for cat, cg in g.groupby("case_category")}
            summ = _summary(g, snapshot, min_n, max_month)
            _write(out / "districts" / f"{did}.json", {
                "id": did, "name": dname, "state_code": st, "state_name": state_name,
                "snapshot_date": str(snapshot.date()), "summary": summ, "categories": cats})
            dist_meta.append({"id": did, "name": dname, "n": int(len(g)),
                              "categories": sorted(c for c, s in cats.items() if not s.get("suppressed"))})
            dist_summaries.append({"id": did, "name": dname, "n": int(len(g)),
                                   "median_days_to_decision": (summ.get("time_to_decision_days") or {}).get("p50"),
                                   "share_undecided_at_3y": summ.get("share_undecided_at_3y"),
                                   "pending_next_gap_over_6m_share": summ.get("pending_next_gap_over_6m_share")})
            cb = cats.get("cheque_bounce")
            if cb and not cb.get("suppressed") and (example is None or cb["n"] > example["n"]):
                example = {"district_id": did, "district_name": dname, "state_name": state_name,
                           "category": "cheque_bounce", "n": cb["n"]}
        state_cats = {cat: group_stats(cg, snapshot, min_n, max_month) for cat, cg in cases.groupby("case_category")}
        _write(out / "states" / f"{st}.json", {
            "code": st, "name": state_name, "snapshot_date": str(snapshot.date()),
            "summary": _summary(cases, snapshot, min_n, max_month), "categories": state_cats,
            "districts": sorted(dist_summaries, key=lambda d: d["name"])})
        meta_states.append({"code": st, "name": state_name, "n": int(len(cases)), "snapshot_date": str(snapshot.date()),
                            "districts": sorted(dist_meta, key=lambda d: d["name"])})
        log.info("state %s %s: %d cases, %d districts", st, state_name, len(cases), len(dist_meta))

    national = {}
    for cat, gs in national_parts.items():
        g = pd.concat(gs, ignore_index=True)
        # each state's pending cases are censored at that state's own snapshot
        stats_parts = []
        for snap, sg in g.groupby("snapshot"):
            stats_parts.append((snap, sg))
        national[cat] = _national_stats(stats_parts, min_n, max_month)
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
        "categories": CATEGORIES,
        "outcome_groups": OUTCOME_GROUPS,
        "example": example,
        "states": sorted(meta_states, key=lambda s: s["name"]),
    }
    _write(out / "meta.json", meta)
    meta["example"] = choose_example(out)
    return meta


def _national_stats(parts: list[tuple[pd.Timestamp, pd.DataFrame]], min_n: int, max_month: int) -> dict:
    """National KM pools durations computed against each state's own snapshot."""
    from .stats import durations_events, kaplan_meier, km_curve, km_quantile

    durs, evs, n = [], [], 0
    frames = []
    for snap, g in parts:
        d, e, _ = durations_events(g, snap)
        durs.append(d)
        evs.append(e)
        n += len(g)
        frames.append(g)
    allg = pd.concat(frames, ignore_index=True)
    base = group_stats(allg, max(s for s, _ in parts), min_n, max_month)  # outcomes, first listing, gaps
    if n < min_n:
        return base
    times, surv = kaplan_meier(np.concatenate(durs), np.concatenate(evs))
    base["time_to_decision_days"] = {"p50": km_quantile(times, surv, 0.5), "p75": km_quantile(times, surv, 0.75),
                                     "p90": km_quantile(times, surv, 0.9), "max_followup": float(times[-1])}
    c = km_curve(times, surv, max_month)
    base["curve_monthly_share_decided"] = c
    base["share_undecided_at_3y"] = round(1 - c[36], 4) if c[36] is not None else None
    base["note"] = "Pooled across states; pending cases are censored at their own last listing date."
    return base


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
