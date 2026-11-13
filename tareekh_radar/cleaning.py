"""Reusable data cleaning: dates, duplicates, categories, stages, chronology, quality report.

Principles:
* Nothing is silently discarded. Rejected and duplicate rows are returned in
  separate frames with a reason, and counted in the quality report.
* Unknown values stay unknown. No imputation of dates, stages or descriptions.
* Vectorised so that millions of case rows (DDL) can be processed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from . import schemas as S
from .ingestion import RawDataset

MISSING_TOKENS = {"", "-", "--", "na", "n/a", "nil", "none", "null", "nan", "nat", "not available",
                  "not recorded", "."}


@dataclass
class CleanDataset:
    cases: pd.DataFrame
    hearings: pd.DataFrame
    rejected: pd.DataFrame
    duplicates: pd.DataFrame
    quality: dict[str, Any] = field(default_factory=dict)
    level: str = "hearing"  # "hearing" if per-hearing records exist, else "case"


# ---------------------------------------------------------------- text helpers

def is_text_dtype(s: pd.Series) -> bool:
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def is_missing_text(value: Any) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return True
    return str(value).strip().lower() in MISSING_TOKENS


def missing_mask(s: pd.Series) -> pd.Series:
    """Vectorised is_missing_text."""
    v = s.astype(object)
    return v.isna() | v.astype(str).str.strip().str.lower().isin(MISSING_TOKENS)


def normalize_text(value: Any) -> str:
    """Lower-case, unify whitespace/punctuation. Missing -> ''."""
    if is_missing_text(value):
        return ""
    s = str(value).lower()
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s*([,;:])\s*", r"\1 ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;")


def _alias_key(value: str) -> str:
    # Orthographic key only: "O.S." / "os" / "O S" -> "os". No semantic merging, because
    # abbreviations mean different things in different states (e.g. "CC", "SC").
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def normalize_case_type(value: Any, aliases: dict[str, list[str]] | None = None) -> str:
    """Map recorded case type to a canonical label. Unmapped values keep their orthographic key."""
    if is_missing_text(value):
        return "UNKNOWN"
    key = _alias_key(str(value))
    for canonical, names in (aliases or {}).items():
        if key == _alias_key(canonical) or key in {_alias_key(n) for n in names}:
            return canonical
    return key.upper() or "UNKNOWN"


def normalize_stage(value: Any, patterns: dict[str, list[str]]) -> str:
    """Map recorded stage text to a canonical stage. Unmatched non-empty -> OTHER; missing -> UNKNOWN."""
    text = normalize_text(value)
    if not text:
        return "UNKNOWN"
    for canonical, pats in patterns.items():
        for pat in pats:
            if re.search(pat, text):
                return canonical
    return "OTHER"


def _map_unique(s: pd.Series, fn) -> pd.Series:
    """Apply fn once per distinct value (fast on millions of rows with few distinct values)."""
    v = s.astype(object)
    uniq = pd.unique(v)
    lookup = {u: fn(u) for u in uniq}
    return v.map(lookup)


# ---------------------------------------------------------------- dates

def parse_dates(
    values: pd.Series, formats: list[str], min_date: str | None, max_date: str | date | None
) -> tuple[pd.Series, pd.Series]:
    """Parse with explicit formats tried in order (no guessing).

    Returns (parsed datetime64 series, status series in {ok, missing, invalid, out_of_range}).
    """
    raw = values.astype(object)
    missing = missing_mask(raw)
    text = raw.astype(str).str.strip()
    # Parse at microsecond resolution so far-out-of-range years (e.g. 0001, 9201) don't overflow.
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[us]")
    remaining = (~missing).copy()
    for fmt in formats:
        if not remaining.any():
            break
        attempt = pd.to_datetime(text[remaining], format=fmt, errors="coerce")
        hit = attempt.notna()
        if hit.any():
            parsed.loc[attempt.index[hit]] = attempt[hit].astype("datetime64[us]")
            remaining.loc[attempt.index[hit]] = False
    status = pd.Series("ok", index=values.index, dtype=object)
    status[missing] = "missing"
    status[(~missing) & parsed.isna()] = "invalid"
    lo = pd.Timestamp(min_date) if min_date else None
    hi = pd.Timestamp(max_date) if max_date else pd.Timestamp(date.today())
    oor = parsed.notna() & (parsed > hi)
    if lo is not None:
        oor |= parsed.notna() & (parsed < lo)
    status[oor] = "out_of_range"
    parsed[oor] = pd.NaT
    return parsed.astype("datetime64[ns]"), status


# ---------------------------------------------------------------- main

def _strip(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if is_text_dtype(out[col]):
            v = out[col].astype(object)
            txt = v.astype(str).str.strip()
            bad = v.isna() | txt.str.lower().isin(["", "nan", "none", "null", "nat"])
            out[col] = txt.where(~bad, None).astype(object)
    return out


def _normalize_status(status: pd.Series, disposal_status: pd.Series, disposal_raw_missing: pd.Series,
                      disposal_nature: pd.Series) -> pd.Series:
    s = status.astype(object).fillna("").astype(str).str.lower()
    out = pd.Series("UNKNOWN", index=status.index, dtype=object)
    has_text = s.str.strip() != ""
    out[s.str.contains("dispos|decided|closed", regex=True)] = "DISPOSED"
    out[s.str.contains("pend", regex=False)] = "PENDING"
    other = has_text & ~out.isin(["DISPOSED", "PENDING"])
    out[other] = s[other].str.upper()
    # No status text: infer only from an unambiguous disposal date.
    no_text = ~has_text
    out[no_text & (disposal_status == "ok")] = "DISPOSED"
    nature_missing = missing_mask(disposal_nature)
    out[no_text & disposal_raw_missing & nature_missing] = "PENDING"
    # disposal nature recorded but no usable date, or an invalid date -> stays UNKNOWN
    return out


def _flags_to_status(flags: list[pd.Series], names: list[str], index) -> pd.Series:
    joined = pd.Series("", index=index, dtype=object)
    for f, n in zip(flags, names):
        m = f.reindex(index, fill_value=False).fillna(False).astype(bool).to_numpy()
        joined = joined + np.where(m, n + "|", "")
    joined = joined.str.rstrip("|")
    return joined.where(joined != "", S.QF_OK).astype(object)


def _flag_counts(status: pd.Series) -> dict[str, int]:
    if status.empty:
        return {}
    return status.str.split("|").explode().value_counts().to_dict()


def clean_cases(raw_cases: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    dcfg = cfg["dates"]
    fmts, min_d, max_d = dcfg["formats"], dcfg.get("min_valid_date"), dcfg.get("max_valid_date")
    cases = _strip(raw_cases)
    rejected = []
    bad = cases["case_id"].isna()
    if bad.any():
        rejected.append(cases[bad].assign(table="cases", reason="blank case_id"))
    cases = cases[~bad]
    dup_mask = cases["case_id"].duplicated(keep="first")
    case_dups = cases[dup_mask].assign(table="cases", reason="duplicate case_id")
    cases = cases[~dup_mask].copy()

    date_cols = ["filing_date", "disposal_date"] + [c for c in S.CASE_LISTING_DATE_COLUMNS if c in cases.columns]
    for c in date_cols:
        cases[f"{c}_raw"] = cases[c]
        cases[c], cases[f"{c}_status"] = parse_dates(cases[f"{c}_raw"], fmts, min_d, max_d)

    f, d = cases["filing_date"], cases["disposal_date"]
    flags, names = [], []

    def add(mask, name):
        flags.append(mask)
        names.append(name)

    for c in date_cols:
        add(cases[f"{c}_status"].isin(["invalid", "out_of_range"]), f"{c}_invalid")
    add(f.notna() & d.notna() & (d < f), "disposal_before_filing")
    cases.loc[f.notna() & d.notna() & (d < f), "disposal_date_status"] = "before_filing"
    if "first_listing_date" in cases:
        fl, ll, nl = cases["first_listing_date"], cases["last_listing_date"], cases["next_listing_date"]
        add(fl.notna() & f.notna() & (fl < f), "first_listing_before_filing")
        add(fl.notna() & ll.notna() & (ll < fl), "last_listing_before_first")
        add(ll.notna() & d.notna() & (ll > d + pd.Timedelta(days=31)), "listing_after_disposal")
        add(nl.notna() & ll.notna() & (nl < ll), "next_listing_before_last")

    aliases = cfg.get("case_type_aliases") or {}
    cases["case_type_raw"] = cases["case_type"]
    cases["case_type"] = _map_unique(cases["case_type_raw"], lambda v: normalize_case_type(v, aliases))
    cases["court_id"] = cases["court_id"].fillna("UNKNOWN")
    for opt in ("case_category", "district_id", "state_code", "current_purpose", "disposal_nature"):
        if opt not in cases.columns:
            cases[opt] = None
    cases["case_category"] = cases["case_category"].fillna("UNKNOWN")
    cases["district_id"] = cases["district_id"].fillna("UNKNOWN")
    cases["state_code"] = cases["state_code"].fillna("UNKNOWN")
    cases["case_status_raw"] = cases["case_status"]
    cases["case_status"] = _normalize_status(
        cases["case_status_raw"], cases["disposal_date_status"], cases["disposal_date_status"] == "missing",
        cases["disposal_nature"])
    add(cases["case_status"] == "UNKNOWN", "status_undetermined")
    stage_patterns = cfg.get("stage_patterns", {})
    cases["current_purpose_stage"] = _map_unique(cases["current_purpose"], lambda v: normalize_stage(v, stage_patterns))

    years = int(cfg["features"].get("filing_cohort_years", 1))
    fy = f.dt.year
    cohort = (fy // years * years).astype("Int64").astype(str)
    cases["filing_cohort"] = np.where(fy.notna(), cohort + (f"+{years}y" if years > 1 else ""), "UNKNOWN")
    cases["data_quality_status"] = _flags_to_status(flags, names, cases.index)
    cases = cases.reset_index(drop=True)
    rej = pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame(columns=["table", "reason"])
    q = {
        "case_duplicate_rows": len(case_dups),
        "date_status": {c: cases[f"{c}_status"].value_counts().to_dict() for c in date_cols},
        "case_flag_counts": _flag_counts(cases["data_quality_status"]),
        "case_status_distribution": cases["case_status"].value_counts().to_dict(),
        "distinct_case_types_raw": int(cases["case_type_raw"].nunique()),
        "distinct_case_types_normalized": int(cases["case_type"].nunique()),
        "current_purpose_stage_distribution": cases["current_purpose_stage"].value_counts().to_dict(),
    }
    return cases, rej, case_dups, q


def clean_hearings(raw_hearings: pd.DataFrame, cases: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    dcfg = cfg["dates"]
    fmts, min_d, max_d = dcfg["formats"], dcfg.get("min_valid_date"), dcfg.get("max_valid_date")
    h = _strip(raw_hearings)
    n_raw = len(h)
    rejected = []
    bad = h["case_id"].isna()
    if bad.any():
        rejected.append(h[bad].assign(table="hearings", reason="blank case_id"))
    h = h[~bad].copy()

    h["hearing_date_raw"] = h["hearing_date"]
    h["hearing_date"], h["date_status"] = parse_dates(h["hearing_date_raw"], fmts, min_d, max_d)
    text_fields = cfg["classification"]["text_fields"]
    pieces = [h[c].astype(object).where(~missing_mask(h[c]), None) for c in text_fields]
    h["event_text"] = [" | ".join(p for p in row if p) for row in zip(*pieces)] if len(h) else pd.Series(dtype=object)
    h["event_text_norm"] = _map_unique(h["event_text"], normalize_text) if len(h) else pd.Series(dtype=object)
    h["text_missing"] = h["event_text_norm"] == ""
    h["hearing_stage_raw"] = h["hearing_stage"]
    stage_patterns = cfg.get("stage_patterns", {})
    h["stage_norm"] = _map_unique(h["hearing_stage_raw"], lambda v: normalize_stage(v, stage_patterns)) if len(h) else pd.Series(dtype=object)

    if "source_row" not in h.columns:
        h["source_row"] = range(len(h))
    no_id = h["hearing_id"].isna()
    if no_id.any():  # generated, traceable ids (never treated as duplicates of each other)
        h.loc[no_id, "hearing_id"] = h.loc[no_id, "case_id"].astype(str) + "#r" + h.loc[no_id, "source_row"].astype(str)
    dup_parts = []
    id_dup = h["hearing_id"].duplicated(keep="first")
    if id_dup.any():
        dup_parts.append(h[id_dup].assign(table="hearings", reason="duplicate hearing_id"))
    h = h[~id_dup]
    keys = cfg["cleaning"]["duplicate_keys"]
    key_frame = h[keys].copy()
    key_frame["hearing_date"] = key_frame["hearing_date"].astype(str)
    content_dup = key_frame.duplicated(keep="first") & h["hearing_date"].notna()
    if content_dup.any():
        dup_parts.append(h[content_dup].assign(table="hearings", reason="duplicate case/date/description"))
    h = h[~content_dup].copy()
    n_dups = int(id_dup.sum() + content_dup.sum())

    known_cases = set(cases["case_id"])
    meta = cases.set_index("case_id")[["filing_date", "disposal_date"]]
    joined = h[["case_id", "hearing_date"]].join(meta, on="case_id")
    dated = h["hearing_date"].notna()
    same_date = h[dated].duplicated(subset=["case_id", "hearing_date"], keep=False).reindex(h.index, fill_value=False)
    src = h[dated].sort_values(["case_id", "source_row"])
    prev = src.groupby("case_id")["hearing_date"].cummax().groupby(src["case_id"]).shift(1)
    out_of_order = (src["hearing_date"] < prev).reindex(h.index, fill_value=False)
    flags = [
        h["date_status"] == "missing", h["date_status"] == "invalid", h["date_status"] == "out_of_range",
        h["text_missing"], ~h["case_id"].isin(known_cases),
        joined["hearing_date"] < joined["filing_date"], joined["hearing_date"] > joined["disposal_date"],
        same_date, out_of_order,
    ]
    names = [S.QF_MISSING_DATE, S.QF_INVALID_DATE, S.QF_OUT_OF_RANGE_DATE, S.QF_MISSING_TEXT, S.QF_ORPHAN,
             S.QF_BEFORE_FILING, S.QF_AFTER_DISPOSAL, S.QF_SAME_DATE, S.QF_SOURCE_ORDER]
    h["data_quality_status"] = _flags_to_status(flags, names, h.index)
    h["date_usable"] = h["hearing_date"].notna()
    h["in_cases_table"] = h["case_id"].isin(known_cases)
    h = h.sort_values(["case_id", "hearing_date", "source_row"], na_position="last").reset_index(drop=True)
    h["seq"] = h.groupby("case_id").cumcount()
    fc = _flag_counts(h["data_quality_status"])
    q = {
        "hearings_raw": n_raw,
        "hearing_duplicate_rows": n_dups,
        "hearing_duplicate_pct": _pct(n_dups, n_raw),
        "hearing_missing_dates": int((h["date_status"] == "missing").sum()),
        "hearing_invalid_dates": int((h["date_status"] == "invalid").sum()),
        "hearing_out_of_range_dates": int((h["date_status"] == "out_of_range").sum()),
        "hearings_missing_description": int(h["text_missing"].sum()),
        "hearings_missing_description_pct": _pct(int(h["text_missing"].sum()), len(h)),
        "hearings_unknown_stage_pct": _pct(int((h["stage_norm"] == "UNKNOWN").sum()), len(h)),
        "hearing_flag_counts": fc,
    }
    rej = pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame(columns=["table", "reason"])
    dups = pd.concat(dup_parts, ignore_index=True) if dup_parts else pd.DataFrame(columns=["table", "reason"])
    return h, rej, dups, q


def empty_hearings() -> pd.DataFrame:
    cols = S.HEARINGS.names + ["source_row", "hearing_date_raw", "date_status", "event_text", "event_text_norm",
                               "text_missing", "hearing_stage_raw", "stage_norm", "date_usable", "in_cases_table", "seq"]
    h = pd.DataFrame({c: pd.Series(dtype=object) for c in cols})
    h["hearing_date"] = pd.Series(dtype="datetime64[ns]")
    return h


def clean_dataset(raw: RawDataset, cfg: dict) -> CleanDataset:
    cases, rej_c, case_dups, qc = clean_cases(raw.cases, cfg)
    has_hearings = raw.hearings is not None and len(raw.hearings) > 0
    if has_hearings:
        h, rej_h, dups_h, qh = clean_hearings(raw.hearings, cases, cfg)
    else:
        h, rej_h, dups_h, qh = empty_hearings(), pd.DataFrame(), pd.DataFrame(), {}
    rejected = pd.concat([x for x in (rej_c, rej_h) if len(x)], ignore_index=True) if (len(rej_c) or len(rej_h)) \
        else pd.DataFrame(columns=["table", "reason"])
    duplicates = pd.concat([x for x in (case_dups, dups_h) if len(x)], ignore_index=True) if (len(case_dups) or len(dups_h)) \
        else pd.DataFrame(columns=["table", "reason"])
    n_cases_raw = len(raw.cases)
    quality = {
        "data_level": "hearing" if has_hearings else "case",
        "rows": {"cases_raw": n_cases_raw, "cases_clean": len(cases),
                 "hearings_raw": len(raw.hearings) if has_hearings else 0, "hearings_clean": len(h),
                 "rejected": len(rejected)},
        "missingness_pct": {
            "cases": _missingness(raw.cases, [c for c in S.CASES.names if c in raw.cases.columns]),
            "hearings": _missingness(raw.hearings, S.HEARINGS.names) if has_hearings else {},
        },
        "duplicates": {"case_duplicate_rows": qc["case_duplicate_rows"],
                       "case_duplicate_pct": _pct(qc["case_duplicate_rows"], n_cases_raw),
                       "hearing_duplicate_rows": qh.get("hearing_duplicate_rows", 0),
                       "hearing_duplicate_pct": qh.get("hearing_duplicate_pct")},
        "cases": qc,
        "hearings": qh,
    }
    return CleanDataset(cases=cases, hearings=h, rejected=rejected, duplicates=duplicates, quality=quality,
                        level="hearing" if has_hearings else "case")


def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 2) if d else None


def _missingness(df: pd.DataFrame, cols: list[str]) -> dict[str, float | None]:
    return {c: _pct(int(missing_mask(df[c]).sum()), len(df)) for c in cols if c in df.columns}
