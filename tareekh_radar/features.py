"""Per-case progression features computed from chronologically ordered, classified hearings.

All definitions are documented in docs/features.md. Key conventions:
* Unknown events are never counted as adjournments. In the primary streak metric an
  UNKNOWN event *breaks* a non-progress streak (conservative); an upper-bound variant
  that lets UNKNOWN continue a streak is reported for sensitivity analysis.
* Procedural progress (notice served, documents filed, appearance) counts as progress.
* Metrics with too few observations are null (NaN) with a reason, not zero.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

ADJ, PROC, SUBST, UNK = "ADJOURNMENT", "PROCEDURAL_PROGRESS", "SUBSTANTIVE_PROGRESS", "UNKNOWN"

FEATURE_COLUMNS = [
    "total_hearings", "dated_hearings", "undated_hearings", "same_day_entries",
    "confirmed_adjournments", "procedural_progress_events", "substantive_progress_events", "unknown_events",
    "adjournment_rate", "adjournment_rate_known",
    "non_progress_streak", "max_non_progress_streak", "max_non_progress_streak_upper",
    "repeated_stage_count", "max_same_stage_run",
    "median_hearing_interval", "maximum_hearing_gap", "max_hearing_gap",
    "days_since_last_substantive", "days_since_last_substantive_basis",
    "unknown_record_percentage", "data_completeness", "case_age_days",
    "current_stage", "first_hearing_date", "last_hearing_date", "observation_end",
    "eligible", "ineligible_reason", "unavailable_metrics", "evidence",
]


def _runs(values: list[Any]) -> list[tuple[Any, int, int]]:
    """Run-length encode -> [(value, start_idx, end_idx_inclusive)]."""
    runs: list[tuple[Any, int, int]] = []
    for i, v in enumerate(values):
        if runs and runs[-1][0] == v:
            runs[-1] = (v, runs[-1][1], i)
        else:
            runs.append((v, i, i))
    return runs


def longest_streak(classes: list[str], unknown_breaks: bool = True) -> tuple[int, int, int]:
    """Longest run of ADJOURNMENT events. Returns (length, start, end); length counts adjournments only."""
    best = (0, -1, -1)
    count, start = 0, None
    for i, c in enumerate(classes):
        if c == ADJ:
            if start is None:
                start = i
            count += 1
            if count > best[0]:
                best = (count, start, i)
        elif c == UNK and not unknown_breaks:
            continue
        else:
            count, start = 0, None
    return best


def trailing_streak(classes: list[str]) -> int:
    n = 0
    for c in reversed(classes):
        if c == ADJ:
            n += 1
        else:
            break
    return n


def stage_returns(stages: list[str]) -> tuple[int, int, list[int]]:
    """(# returns to a previously left stage, longest same-stage run, indices where a return starts)."""
    known = [(i, s) for i, s in enumerate(stages) if s not in ("UNKNOWN", None, "")]
    if not known:
        return 0, 0, []
    idxs, vals = zip(*known)
    runs = _runs(list(vals))
    seen: set[str] = set()
    returns: list[int] = []
    for v, s, _e in runs:
        if v in seen:
            returns.append(idxs[s])
        seen.add(v)
    longest = max(e - s + 1 for _v, s, e in runs)
    return len(returns), longest, returns


def compute_case_features(
    cases: pd.DataFrame, hearings: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    fcfg = cfg["features"]
    """Return one row per case. Hearing features need per-hearing records; case-level
    listing features need listing dates. Whichever is unavailable stays null."""
    min_rates = int(fcfg["min_hearings_for_rates"])
    min_int = int(fcfg["min_hearings_for_intervals"])
    max_unknown = float(fcfg["max_unknown_share_for_eligibility"])
    has_hearings = hearings is not None and len(hearings) > 0
    level = "hearing" if has_hearings else "case"
    keep = ["case_id", "court_id", "court_name", "case_type", "case_type_raw", "case_category", "case_status",
            "filing_cohort", "district_id", "district_name", "state_code", "state_name", "source_reference",
            "current_purpose", "disposal_nature", "data_quality_status", "filing_date", "disposal_date",
            "first_listing_date", "last_listing_date", "next_listing_date"]
    meta = cases[[c for c in keep if c in cases.columns]].rename(columns={"data_quality_status": "case_quality_status"})

    case_feats, case_ref = _case_level_features(cases, cfg)
    feats = meta.merge(case_feats, on="case_id", how="left")

    if has_hearings:
        h = hearings[hearings["in_cases_table"]] if "in_cases_table" in hearings else hearings
        ref = fcfg.get("reference_date")
        reference_date = pd.Timestamp(ref) if ref else h["hearing_date"].max()
        if pd.isna(reference_date):
            reference_date = pd.Timestamp.today().normalize()
        groups = {cid: g for cid, g in h.groupby("case_id", sort=False)}
        rows = [_features_for_case(case, groups.get(case.case_id), reference_date, min_rates, min_int, max_unknown)
                for case in cases.itertuples(index=False)]
        hf = pd.DataFrame(rows)
        feats = feats.merge(hf, on="case_id", how="left")
        feats["current_stage"] = feats["current_stage"].fillna("UNKNOWN")
        feats.attrs["reference_date"] = str(reference_date.date())
    else:
        for c in FEATURE_COLUMNS:
            if c not in feats.columns:
                feats[c] = np.nan
        feats["current_stage"] = cases["current_purpose_stage"].to_numpy() if "current_purpose_stage" in cases else "UNKNOWN"
        feats["eligible"] = feats["case_eligible"]
        feats["ineligible_reason"] = feats["case_ineligible_reason"]
        feats["unavailable_metrics"] = json.dumps({"hearing_metrics": "source has no per-hearing records"})
        feats["evidence"] = "{}"
        feats["days_since_last_substantive_basis"] = "unavailable"
        feats["data_completeness"] = feats["case_data_completeness"]
        feats.attrs["reference_date"] = str(case_ref.date())
    feats.attrs["data_level"] = level
    return feats


CASE_FEATURE_COLUMNS = ["case_age_days", "days_to_first_listing", "days_since_last_listing", "next_listing_gap",
                        "listing_span_days", "case_data_completeness", "case_eligible", "case_ineligible_reason",
                        "case_observation_end"]


def _case_level_features(cases: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Vectorised features from case-level dates (filing, decision, first/last/next listing)."""
    fcfg = cfg["features"]
    out = pd.DataFrame({"case_id": cases["case_id"]})
    f = cases["filing_date"]
    d = cases["disposal_date"]
    has_listing = "first_listing_date" in cases.columns
    fl = cases["first_listing_date"] if has_listing else pd.Series(pd.NaT, index=cases.index)
    ll = cases["last_listing_date"] if has_listing else pd.Series(pd.NaT, index=cases.index)
    nl = cases["next_listing_date"] if has_listing else pd.Series(pd.NaT, index=cases.index)
    ref_cfg = fcfg.get("case_reference_date")
    if ref_cfg:
        ref = pd.Timestamp(ref_cfg)
    else:
        # Snapshot proxy: latest recorded listing or decision in the data (invalid dates already removed).
        ref = pd.concat([ll, d]).max()
        if pd.isna(ref):
            ref = pd.Timestamp.today().normalize()
    status = cases["case_status"]
    pending, disposed = status == "PENDING", status == "DISPOSED"
    obs_end = pd.Series(pd.NaT, index=cases.index, dtype="datetime64[ns]")
    obs_end[disposed & d.notna()] = d[disposed & d.notna()]
    obs_end[pending] = ref
    out["case_observation_end"] = obs_end

    def days(a, b):
        return (a - b).dt.days.astype("float")

    age = days(obs_end, f)
    out["case_age_days"] = age.where(age >= 0)
    ttf = days(fl, f)
    out["days_to_first_listing"] = ttf.where(ttf >= 0)
    since = days(pd.Series(ref, index=cases.index), ll)
    out["days_since_last_listing"] = since.where(pending & (since >= 0))
    gap = days(nl, ll)
    out["next_listing_gap"] = gap.where(pending & (gap >= 0))
    span = days(ll, fl)
    out["listing_span_days"] = span.where(span >= 0)

    applicable = pd.DataFrame({
        "filing": f.notna(),
        "first": fl.notna(),
        "last": ll.notna(),
        "purpose": ~cases.get("current_purpose", pd.Series(None, index=cases.index)).isna(),
        "outcome": np.where(disposed, d.notna(), np.where(pending, nl.notna(), False)),
    })
    out["case_data_completeness"] = applicable.mean(axis=1).round(4)

    reasons = pd.Series("", index=cases.index, dtype=object)
    for mask, why in [
        (f.isna(), "filing_date_unusable;"),
        (cases["case_type"] == "UNKNOWN", "case_type_unknown;"),
        (~status.isin(["PENDING", "DISPOSED"]), "status_undetermined;"),
        (has_listing and ll.isna(), "no_valid_last_listing_date;") if has_listing else (pd.Series(False, index=cases.index), ""),
        (cases["court_id"] == "UNKNOWN", "court_unknown;"),
    ]:
        reasons = reasons + np.where(mask, why, "")
    reasons = reasons.str.rstrip(";")
    out["case_eligible"] = reasons == ""
    out["case_ineligible_reason"] = reasons.where(reasons != "", None)
    return out, ref


def _features_for_case(case, g: pd.DataFrame | None, reference_date, min_rates, min_int, max_unknown) -> dict:
    out: dict[str, Any] = {"case_id": case.case_id}
    unavailable: dict[str, str] = {}
    if g is None or len(g) == 0:
        out.update({k: np.nan for k in FEATURE_COLUMNS})
        out.update(total_hearings=0, dated_hearings=0, undated_hearings=0, eligible=False,
                   ineligible_reason="no_hearings_recorded", unavailable_metrics=json.dumps({"all": "no hearings"}),
                   evidence=json.dumps({}), current_stage="UNKNOWN", days_since_last_substantive_basis="unavailable")
        return out

    classes_all = g["event_class"].tolist()
    total = len(g)
    n_adj = classes_all.count(ADJ)
    n_proc = classes_all.count(PROC)
    n_sub = classes_all.count(SUBST)
    n_unk = classes_all.count(UNK)
    known = total - n_unk

    d = g[g["date_usable"]].sort_values(["hearing_date", "source_row"])
    n_dated = len(d)
    classes = d["event_class"].tolist()
    ids = d["hearing_id"].tolist()
    dates = d["hearing_date"].tolist()

    out.update(total_hearings=total, dated_hearings=n_dated, undated_hearings=total - n_dated,
               confirmed_adjournments=n_adj, procedural_progress_events=n_proc,
               substantive_progress_events=n_sub, unknown_events=n_unk)
    out["unknown_record_percentage"] = round(100.0 * n_unk / total, 2)
    complete = int(((g["event_class"] != UNK) & g["date_usable"]).sum())
    out["data_completeness"] = round(complete / total, 4)
    evidence: dict[str, Any] = {"adjournment_hearing_ids": g.loc[g["event_class"] == ADJ, "hearing_id"].tolist()}

    # rates
    if total >= min_rates:
        out["adjournment_rate"] = round(n_adj / total, 4)
        out["adjournment_rate_known"] = round(n_adj / known, 4) if known else np.nan
        if not known:
            unavailable["adjournment_rate_known"] = "all events unknown"
    else:
        out["adjournment_rate"] = out["adjournment_rate_known"] = np.nan
        unavailable["adjournment_rate"] = f"fewer than {min_rates} hearings"

    # streaks (chronological)
    if n_dated >= min_rates:
        L, s, e = longest_streak(classes, unknown_breaks=True)
        Lu, _, _ = longest_streak(classes, unknown_breaks=False)
        out["max_non_progress_streak"] = L
        out["max_non_progress_streak_upper"] = Lu
        out["non_progress_streak"] = trailing_streak(classes)
        evidence["max_streak_hearing_ids"] = ids[s: e + 1] if L else []
    else:
        out["max_non_progress_streak"] = out["max_non_progress_streak_upper"] = out["non_progress_streak"] = np.nan
        unavailable["max_non_progress_streak"] = f"fewer than {min_rates} dated hearings"

    # stages
    stage_keys = [
        (f"OTHER:{str(r).strip().lower()}" if s_ == "OTHER" else s_)
        for s_, r in zip(d["stage_norm"], d["hearing_stage_raw"])
    ]
    n_stage_known = sum(1 for s_ in stage_keys if s_ != "UNKNOWN")
    if n_stage_known >= min_rates:
        rets, longest, ret_idx = stage_returns(stage_keys)
        out["repeated_stage_count"] = rets
        out["max_same_stage_run"] = longest
        evidence["stage_return_hearing_ids"] = [ids[i] for i in ret_idx]
    else:
        out["repeated_stage_count"] = out["max_same_stage_run"] = np.nan
        unavailable["repeated_stage_count"] = f"fewer than {min_rates} hearings with a recorded stage"
    known_stages = [s_ for s_ in d["stage_norm"].tolist() if s_ != "UNKNOWN"]
    out["current_stage"] = known_stages[-1] if known_stages else "UNKNOWN"

    # intervals on distinct dates
    uniq = d.drop_duplicates("hearing_date")
    out["same_day_entries"] = n_dated - len(uniq)
    if len(uniq) >= min_int:
        gaps = uniq["hearing_date"].diff().dt.days.iloc[1:].to_numpy()
        out["median_hearing_interval"] = float(np.median(gaps))
        j = int(np.argmax(gaps))
        out["maximum_hearing_gap"] = out["max_hearing_gap"] = float(gaps[j])
        evidence["max_gap_hearing_ids"] = [uniq["hearing_id"].iloc[j], uniq["hearing_id"].iloc[j + 1]]
    else:
        out["median_hearing_interval"] = out["maximum_hearing_gap"] = out["max_hearing_gap"] = np.nan
        unavailable["max_hearing_gap"] = f"fewer than {min_int} distinct hearing dates"

    # observation window
    disposal = case.disposal_date if getattr(case, "disposal_date_status", "ok") == "ok" else pd.NaT
    obs_end = disposal if pd.notna(disposal) else reference_date
    if n_dated:
        obs_end = max(obs_end, dates[-1])
        out["first_hearing_date"], out["last_hearing_date"] = dates[0], dates[-1]
    else:
        out["first_hearing_date"] = out["last_hearing_date"] = pd.NaT
    out["observation_end"] = obs_end
    filing = case.filing_date if getattr(case, "filing_date_status", "ok") == "ok" else pd.NaT
    out["case_age_days"] = float((obs_end - filing).days) if pd.notna(filing) else np.nan
    if pd.isna(filing):
        unavailable["case_age_days"] = "filing date missing/invalid"

    # days since last substantive progress
    if n_dated >= min_rates and any(c_ != UNK for c_ in classes):
        sub_idx = [i for i, c_ in enumerate(classes) if c_ == SUBST]
        if sub_idx:
            last = sub_idx[-1]
            out["days_since_last_substantive"] = float((obs_end - dates[last]).days)
            out["days_since_last_substantive_basis"] = "since_last_substantive_event"
            evidence["last_substantive_hearing_id"] = ids[last]
        else:
            out["days_since_last_substantive"] = float((obs_end - dates[0]).days)
            out["days_since_last_substantive_basis"] = "no_substantive_event_since_first_hearing"
            evidence["last_substantive_hearing_id"] = None
    else:
        out["days_since_last_substantive"] = np.nan
        out["days_since_last_substantive_basis"] = "unavailable"
        unavailable["days_since_last_substantive"] = "too few dated hearings or all events unknown"

    # eligibility for anomaly scoring
    reasons = []
    if n_dated < min_rates:
        reasons.append(f"fewer_than_{min_rates}_dated_hearings")
    if total and n_unk / total > max_unknown:
        reasons.append(f"unknown_share_above_{max_unknown:.0%}")
    if str(case.case_type) == "UNKNOWN":
        reasons.append("case_type_unknown")
    out["eligible"] = not reasons
    out["ineligible_reason"] = ";".join(reasons) if reasons else None
    out["unavailable_metrics"] = json.dumps(unavailable)
    out["evidence"] = json.dumps(evidence, default=str)
    return out
