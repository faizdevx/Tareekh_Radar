"""Explainable anomaly detection.

1. Statistical baseline (primary): robust, one-sided peer-group comparison.
   For each eligible case a comparison group of similar cases is chosen from a
   configured hierarchy of peer definitions (always within the same case type or
   category, and - in case mode - the same pending/disposed status).
   Each feature gets a robust z-score  z = (x - median) / scale  with
   scale = max(1.4826 * MAD, IQR / 1.349, floor)  and an empirical mid-rank percentile.
   A feature *contributes* to a flag only if z >= z_threshold, percentile >=
   percentile_threshold and the raw value >= min_abs.
2. Isolation Forest (experimental comparison): features robust-scaled within
   (case type, status) groups, fitted separately for pending and disposed cases.
3. Raw baselines: rank by un-normalised feature values (see evaluation.py).

Data completeness is reported alongside but never folded into the anomaly score.
Everything is vectorised (groupby) so millions of cases can be scored.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from . import DISCLAIMER

FEATURE_LABELS = {
    # hearing mode
    "adjournment_rate": "confirmed adjournment rate",
    "max_non_progress_streak": "longest run of consecutive confirmed adjournments",
    "repeated_stage_count": "returns to a previously recorded procedural stage",
    "days_since_last_substantive": "days since the last recorded substantive progress",
    "max_hearing_gap": "longest interval between consecutive hearings (days)",
    # case mode
    "case_age_days": "case duration in days (filing to decision, or to data snapshot if pending)",
    "days_since_last_listing": "days since the last recorded listing (pending cases)",
    "days_to_first_listing": "days from filing to first listing",
    "next_listing_gap": "days between last listing and the next scheduled listing (pending cases)",
}

LEGITIMATE_EXPLANATIONS = {
    "adjournment_rate": ["presiding officer vacancy, leave or transfer", "service of summons/notice pending",
                         "stay or record called for by a higher court", "multiple parties whose presence is required",
                         "advocates' strike or court-wide disruption"],
    "max_non_progress_streak": ["case awaiting an outcome elsewhere (connected matter, higher-court stay)",
                                "court not functioning on those dates", "witnesses or records unavailable"],
    "repeated_stage_count": ["remand or recall of witnesses ordered by the court",
                             "amendment of pleadings or additional evidence permitted",
                             "inconsistent stage recording in the source system"],
    "days_since_last_substantive": ["case sine die / stayed / transferred", "awaiting expert reports or records",
                                    "missing or unrecorded orders in the source data"],
    "max_hearing_gap": ["court vacations or long-term vacancy", "case consigned to record room and revived later",
                        "hearings not uploaded for that period (data gap)"],
    "case_age_days": ["complex matter (many parties, witnesses or charges)", "stay by a higher court",
                      "accused absconding / warrant pending", "transfer between courts restarting the record",
                      "court vacancy or heavy docket in that establishment"],
    "days_since_last_listing": ["case adjourned sine die or stayed", "case consigned to record room (dormant file)",
                                "listing not updated in the eCourts record at the time of the snapshot (data gap)"],
    "days_to_first_listing": ["service of summons on accused/defendant pending", "registration/scrutiny delays",
                              "first listing not entered in the eCourts record (data gap)"],
    "next_listing_gap": ["long date given due to court vacation or docket", "case awaiting a report or a higher-court outcome",
                         "next date recorded incorrectly in the source"],
}

LIMITATIONS = {
    "hearing": [
        "Event classes are inferred from recorded text and may be wrong; UNKNOWN events are never counted as adjournments.",
        "Peer groups contain only cases present in this dataset; they are not a legal or official standard.",
        "Recorded hearing histories may be incomplete; gaps can reflect missing uploads rather than inactivity.",
        "The score is a relative statistical deviation, not a probability and not evidence of misconduct.",
    ],
    "case": [
        "Case-level source: no per-hearing history, so adjournments and non-progress streaks cannot be observed.",
        "Durations depend on dates as recorded in eCourts at the time of the DDL snapshot; dates may be stale or wrong.",
        "The data snapshot date is approximated by the latest recorded listing/decision date in the dataset.",
        "Peer groups contain only cases present in this dataset; they are not a legal or official standard.",
        "The score is a relative statistical deviation, not a probability and not evidence of misconduct.",
    ],
}

UNKNOWN_TOKENS = ["UNKNOWN", "nan", "None", "<NA>", "NaT", ""]


def mode_config(cfg: dict, mode: str) -> dict:
    return cfg["anomaly"]["modes"][mode]


def _key(df: pd.DataFrame, dims: list[str]) -> tuple[pd.Series, pd.Series]:
    s = df[dims[0]].astype(str)
    unknown = s.isin(UNKNOWN_TOKENS)
    for d in dims[1:]:
        v = df[d].astype(str)
        s = s + " | " + v
        unknown |= v.isin(UNKNOWN_TOKENS)
    return s, unknown


def assign_peer_groups(features: pd.DataFrame, cfg: dict, mode: str) -> tuple[pd.DataFrame, dict[int, tuple]]:
    """Pick the most specific peer level with >= min_peer_size eligible cases."""
    min_size = int(cfg["anomaly"]["min_peer_size"])
    df = features.copy()
    df["peer_level"] = pd.Series(None, index=df.index, dtype=object)
    df["peer_group_key"] = pd.Series(None, index=df.index, dtype=object)
    df["peer_group_size"] = np.nan
    elig = df["eligible"].fillna(False).astype(bool)
    level_keys: dict[int, tuple] = {}
    for li, level in enumerate(mode_config(cfg, mode)["peer_levels"]):
        dims = [c for c in level if c in df.columns]
        if len(dims) != len(level):
            continue  # a dimension this source does not have
        key, unknown = _key(df, dims)
        members = elig & ~unknown
        size = key.map(key[members].value_counts()).fillna(0)
        take = members & df["peer_level"].isna() & (size >= min_size)
        df.loc[take, "peer_level"] = f"{li}:" + "+".join(dims)
        df.loc[take, "peer_group_key"] = key[take]
        df.loc[take, "peer_group_size"] = size[take]
        level_keys[li] = (dims, key, members)
    return df, level_keys


def score_statistical(features: pd.DataFrame, cfg: dict, mode: str | None = None) -> pd.DataFrame:
    acfg = cfg["anomaly"]
    mode = mode or features.attrs.get("data_level", "hearing")
    fspec: dict[str, dict] = mode_config(cfg, mode)["features"]
    z_thr, p_thr = float(acfg["z_threshold"]), float(acfg["percentile_threshold"])
    min_size = int(acfg["min_peer_size"])
    df, level_keys = assign_peer_groups(features, cfg, mode)
    df.attrs.update(features.attrs)
    df.attrs["data_level"] = mode
    elig = df["eligible"].fillna(False).astype(bool)

    for f in fspec:
        for suffix in ("peer_median", "peer_q1", "peer_q3", "peer_n", "z", "pct"):
            df[f"{f}_{suffix}"] = np.nan
    for li, (dims, key, members) in level_keys.items():
        assigned = df["peer_level"].str.startswith(f"{li}:", na=False)
        if not assigned.any():
            continue
        mkey = key[members]
        for f, spec in fspec.items():
            x = df.loc[members, f].astype(float)
            g = x.groupby(mkey)
            med = g.median()
            q1, q3 = g.quantile(0.25), g.quantile(0.75)
            n = g.count()
            mad = (x - mkey.map(med)).abs().groupby(mkey).median()
            scale = np.maximum(np.maximum(1.4826 * mad, (q3 - q1) / 1.349), float(spec.get("floor", 0.0)))
            rank = g.rank(method="average")
            pct = (rank - 0.5) / mkey.map(n)
            akey = key[assigned]
            ok = akey.map(n).fillna(0) >= min_size
            idx = akey.index[ok.to_numpy()]
            ak = akey[ok]
            xa = df.loc[idx, f].astype(float)
            df.loc[idx, f"{f}_peer_median"] = ak.map(med).to_numpy()
            df.loc[idx, f"{f}_peer_q1"] = ak.map(q1).to_numpy()
            df.loc[idx, f"{f}_peer_q3"] = ak.map(q3).to_numpy()
            df.loc[idx, f"{f}_peer_n"] = ak.map(n).to_numpy()
            df.loc[idx, f"{f}_z"] = ((xa - ak.map(med)) / ak.map(scale)).round(3).to_numpy()
            df.loc[idx, f"{f}_pct"] = pct.reindex(idx).round(4).to_numpy()

    scored = df["peer_level"].notna()
    zcols = [f"{f}_z" for f in fspec]
    df["anomaly_score"] = np.nan
    df.loc[scored, "anomaly_score"] = df.loc[scored, zcols].clip(lower=0).max(axis=1, skipna=True).fillna(0.0).round(3)
    df["score_status"] = np.where(scored, "scored",
                                  np.where(elig, "no_comparable_peer_group", "ineligible:" + df["ineligible_reason"].fillna("").astype(str)))

    contrib_z = pd.DataFrame(index=df.index)
    for f, spec in fspec.items():
        c = (df[f"{f}_z"] >= z_thr) & (df[f"{f}_pct"] >= p_thr) & (df[f].astype(float) >= float(spec.get("min_abs", 0))) & scored
        contrib_z[f] = df[f"{f}_z"].where(c)
    df["flagged"] = contrib_z.notna().any(axis=1)
    df["contributing_features"] = "[]"
    fl = df["flagged"]
    if fl.any():
        df.loc[fl, "contributing_features"] = contrib_z[fl].apply(
            lambda r: json.dumps([k for k, _ in sorted(r.dropna().items(), key=lambda kv: -kv[1])]), axis=1)
    top = contrib_z.max(axis=1)
    sev = acfg["severity"]
    df["severity"] = np.select([~fl, top >= sev["high"], top >= sev["medium"]], ["none", "high", "medium"], "low")

    df["anomaly_percentile"] = np.nan
    if scored.any():
        grp = df.loc[scored, "peer_level"] + "##" + df.loc[scored, "peer_group_key"]
        r = df.loc[scored, "anomaly_score"].groupby(grp).rank(method="average")
        df.loc[scored, "anomaly_percentile"] = ((r - 0.5) / grp.map(grp.value_counts())).round(4)

    # Separate data-quality problems from analytical findings: a flag on a case whose source
    # record has quality issues (e.g. listing after disposal) may be a data artefact.
    qcol = df["case_quality_status"] if "case_quality_status" in df else pd.Series("ok", index=df.index)
    df["flag_has_quality_issue"] = fl & qcol.fillna("ok").ne("ok")
    df["anomaly_explanation_json"] = None
    if fl.any():
        df.loc[fl, "anomaly_explanation_json"] = df[fl].apply(
            lambda r: json.dumps(build_explanation(r, fspec, mode), default=str), axis=1)
    df["anomaly_explanation"] = np.select(
        [fl, scored, df["score_status"] == "no_comparable_peer_group"],
        ["", "No feature deviates beyond the configured thresholds relative to comparable cases.",
         "Not scored: no comparable peer group with enough eligible cases."],
        "Not scored: " + df["score_status"].str.replace("ineligible:", "", regex=False).str.replace("_", " "))
    if fl.any():
        df.loc[fl, "anomaly_explanation"] = df.loc[fl, "anomaly_explanation_json"].map(lambda s: json.loads(s)["summary"])
    return df


# ---------------------------------------------------------------- explanations

def _fmt(f: str, v: Any) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    if f == "adjournment_rate":
        return f"{v:.0%}"
    return f"{v:,.0f}"


def _date(v) -> str:
    return "n/a" if v is None or pd.isna(v) else str(pd.Timestamp(v).date())


def _base_sentence(f: str, row: pd.Series) -> str:
    v = row[f]
    if f == "adjournment_rate":
        return (f"Unusually high confirmed adjournment rate: {_fmt(f, v)} "
                f"({int(row['confirmed_adjournments'])} of {int(row['total_hearings'])} recorded hearings)")
    if f == "max_non_progress_streak":
        return f"Unusually long sequence of non-progress hearings: {_fmt(f, v)} consecutive confirmed adjournments"
    if f == "repeated_stage_count":
        return f"Repeated returns to an earlier recorded procedural stage: {_fmt(f, v)} returns"
    if f == "days_since_last_substantive":
        extra = " (no substantive event recorded at all)" if row.get("days_since_last_substantive_basis") == \
            "no_substantive_event_since_first_hearing" else ""
        return f"Unusually prolonged interval since the last recorded substantive progress: {_fmt(f, v)} days{extra}"
    if f == "max_hearing_gap":
        return f"Unusually long gap between consecutive hearings: {_fmt(f, v)} days"
    if f == "case_age_days":
        state = "still pending at the data snapshot" if row.get("case_status") == "PENDING" else "until decision"
        return f"Unusually long case duration: {_fmt(f, v)} days from filing ({state})"
    if f == "days_since_last_listing":
        return (f"Unusually long period without a recorded listing: {_fmt(f, v)} days since the last listing "
                f"on {_date(row.get('last_listing_date'))} while the case is recorded as pending")
    if f == "days_to_first_listing":
        return f"Unusually long delay before the first listing: {_fmt(f, v)} days after filing"
    if f == "next_listing_gap":
        return f"Unusually long gap to the next scheduled listing: {_fmt(f, v)} days"
    return f"{FEATURE_LABELS.get(f, f)}: {_fmt(f, v)}"


def _sentence(f: str, row: pd.Series) -> str:
    med, q1, q3, pct = row[f"{f}_peer_median"], row[f"{f}_peer_q1"], row[f"{f}_peer_q3"], row[f"{f}_pct"]
    return (f"{_base_sentence(f, row)}, versus a peer median of {_fmt(f, med)} (IQR {_fmt(f, q1)}-{_fmt(f, q3)}); "
            f"{pct:.0%} of comparable cases have a value at or below this.")


def _supporting(f: str, row: pd.Series) -> dict[str, Any]:
    evidence = json.loads(row["evidence"]) if isinstance(row.get("evidence"), str) and row.get("evidence") else {}
    hearing_ids = {
        "adjournment_rate": evidence.get("adjournment_hearing_ids", []),
        "max_non_progress_streak": evidence.get("max_streak_hearing_ids", []),
        "repeated_stage_count": evidence.get("stage_return_hearing_ids", []),
        "days_since_last_substantive": [evidence["last_substantive_hearing_id"]] if evidence.get("last_substantive_hearing_id") else [],
        "max_hearing_gap": evidence.get("max_gap_hearing_ids", []),
    }.get(f)
    if hearing_ids is not None:
        return {"supporting_hearing_ids": hearing_ids}
    fields = {"case_age_days": ["filing_date", "disposal_date", "case_observation_end"],
              "days_since_last_listing": ["last_listing_date", "case_observation_end"],
              "days_to_first_listing": ["filing_date", "first_listing_date"],
              "next_listing_gap": ["last_listing_date", "next_listing_date"]}.get(f, [])
    return {"supporting_record": row.get("source_reference"),
            "supporting_fields": {k: _date(row.get(k)) for k in fields}}


def build_explanation(row: pd.Series, fspec: dict, mode: str = "hearing") -> dict[str, Any]:
    contrib = json.loads(row.get("contributing_features") or "[]")
    um = row.get("unavailable_metrics")
    completeness = {
        "data_completeness": row.get("data_completeness"),
        "case_quality_flags": row.get("case_quality_status"),
        "total_hearings": row.get("total_hearings"),
        "unknown_record_percentage": row.get("unknown_record_percentage"),
        "unavailable_metrics": json.loads(um) if isinstance(um, str) and um else {},
    }
    status = row["score_status"]
    if status != "scored":
        reason = ("No comparable peer group with enough eligible cases; the case is not scored."
                  if status == "no_comparable_peer_group" else
                  f"Not scored: {status.split(':', 1)[-1] or 'insufficient data'}.")
        return {"summary": reason, "status": status, "contributions": [], "peer_group": None, "mode": mode,
                "data_completeness": completeness, "limitations": LIMITATIONS[mode], "disclaimer": DISCLAIMER}
    contributions = []
    for f in contrib:
        contributions.append({
            "feature": f, "label": FEATURE_LABELS.get(f, f), "value": row[f],
            "peer_median": row[f"{f}_peer_median"], "peer_q1": row[f"{f}_peer_q1"], "peer_q3": row[f"{f}_peer_q3"],
            "peer_n_with_value": row.get(f"{f}_peer_n"), "robust_z": row[f"{f}_z"], "peer_percentile": row[f"{f}_pct"],
            "sentence": _sentence(f, row),
            "possible_legitimate_explanations": LEGITIMATE_EXPLANATIONS.get(f, []),
            **_supporting(f, row),
        })
    dims = row["peer_level"].split(":", 1)[1].split("+")
    peer = {"dimensions": dims, "key": row["peer_group_key"], "size": int(row["peer_group_size"]),
            "definition": "Eligible cases in this dataset sharing " + ", ".join(dims) + " = " + str(row["peer_group_key"])}
    caveat = ""
    if pd.notna(row.get("unknown_record_percentage")) and row["unknown_record_percentage"] >= 25:
        caveat = f" Caution: {row['unknown_record_percentage']:.0f}% of this case's hearing records are UNKNOWN."
    q = row.get("case_quality_status")
    if isinstance(q, str) and q != "ok":
        caveat += f" Data-quality flags on this case: {q.replace('|', ', ')}."
    summary = (" ".join(c["sentence"] for c in contributions) if contributions else
               "No feature deviates beyond the configured thresholds relative to comparable cases.") + caveat
    return {"summary": summary, "status": status, "mode": mode, "contributions": contributions, "peer_group": peer,
            "anomaly_score": row["anomaly_score"], "anomaly_percentile": row.get("anomaly_percentile"),
            "severity": row.get("severity"), "data_completeness": completeness,
            "limitations": LIMITATIONS[mode], "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------- isolation forest

def score_isolation_forest(features: pd.DataFrame, cfg: dict, mode: str | None = None) -> pd.DataFrame:
    """Experimental: Isolation Forest, fitted per case status on robust-scaled features."""
    acfg = cfg["anomaly"]
    icfg = acfg["isolation_forest"]
    mode = mode or features.attrs.get("data_level", "hearing")
    cols_all = list(mode_config(cfg, mode)["features"].keys())
    floors = {f: float(s.get("floor", 1.0)) for f, s in mode_config(cfg, mode)["features"].items()}
    min_size = int(acfg["min_peer_size"])
    out = pd.DataFrame({"case_id": features["case_id"]}, index=features.index)
    out["if_score"] = np.nan
    elig = features["eligible"].fillna(False).astype(bool)
    out["if_status"] = np.where(elig, "not_scored", "ineligible")
    type_col = "case_type" if "case_type" in features else "case_category"
    rng = np.random.default_rng(int(icfg["random_state"]))
    for status, sg in features[elig].groupby("case_status"):
        cols = [c for c in cols_all if sg[c].notna().mean() >= 0.5]
        if not cols:
            out.loc[sg.index, "if_status"] = "no_usable_features"
            continue
        complete = sg[sg[cols].notna().all(axis=1)]
        out.loc[sg.index.difference(complete.index), "if_status"] = "missing_features"
        X = complete[cols].astype(float)
        grp = complete[type_col].astype(str)
        sizes = grp.map(grp.value_counts())
        small = sizes < min_size
        out.loc[complete.index[small.to_numpy()], "if_status"] = "type_group_too_small"
        X, grp = X[~small], grp[~small]
        if len(X) < min_size:
            continue
        med = X.groupby(grp).transform("median")
        iqr = X.groupby(grp).transform(lambda s: s.quantile(0.75) - s.quantile(0.25))
        scale = iqr.clip(lower=pd.Series(floors)[cols], axis=1)
        Xs = ((X - med) / scale).to_numpy()
        fit_idx = np.arange(len(Xs))
        if len(Xs) > int(icfg["max_fit_rows"]):
            fit_idx = rng.choice(len(Xs), int(icfg["max_fit_rows"]), replace=False)
        model = IsolationForest(n_estimators=icfg["n_estimators"], contamination=icfg["contamination"],
                                max_samples=min(int(icfg["max_samples"]), len(fit_idx)) if str(icfg["max_samples"]).isdigit() else icfg["max_samples"], random_state=icfg["random_state"], n_jobs=-1)
        model.fit(Xs[fit_idx])
        out.loc[X.index, "if_score"] = np.round(-model.score_samples(Xs), 4)
        out.loc[X.index, "if_status"] = f"scored:{status}:" + ",".join(cols)
    out["if_flag"] = False
    sc = out["if_score"].notna()
    if sc.any():
        k = max(1, int(np.ceil(float(icfg["top_fraction"]) * sc.sum())))
        thr = out.loc[sc, "if_score"].nlargest(k).min()
        out["if_flag"] = out["if_score"] >= thr
    return out


def run_anomaly_detection(features: pd.DataFrame, cfg: dict, mode: str | None = None) -> pd.DataFrame:
    mode = mode or features.attrs.get("data_level", "hearing")
    stat = score_statistical(features, cfg, mode)
    iso = score_isolation_forest(features, cfg, mode)
    res = stat.merge(iso, on="case_id", how="left")
    res.attrs.update(stat.attrs)
    return res
