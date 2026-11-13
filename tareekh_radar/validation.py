"""Structural validation of loaded (contract-shaped) data before cleaning."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .ingestion import IngestionError, RawDataset
from .schemas import CASES, HEARINGS


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int | float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "stats": self.stats}


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def validate_raw(raw: RawDataset) -> ValidationReport:
    """Check the data contract. Errors are fatal; warnings are reported and carried forward."""
    rep = ValidationReport()
    c, h = raw.cases, raw.hearings
    for schema, df in ((CASES, c), (HEARINGS, h)):
        absent = [col for col in schema.names if col not in df.columns]
        if absent:
            rep.errors.append(f"{schema.name}: columns absent after mapping: {absent}")
    if rep.errors:
        return rep

    rep.stats["cases_rows"] = len(c)
    rep.stats["hearings_rows"] = len(h)
    blank_case_ids = int(_blank(c["case_id"]).sum())
    blank_h_case_ids = int(_blank(h["case_id"]).sum())
    rep.stats["cases_blank_case_id"] = blank_case_ids
    rep.stats["hearings_blank_case_id"] = blank_h_case_ids
    if blank_case_ids == len(c):
        rep.errors.append("cases: every row has a blank case_id")
    if len(h) and blank_h_case_ids == len(h):
        rep.errors.append("hearings: every row has a blank case_id")
    if blank_case_ids:
        rep.warnings.append(f"cases: {blank_case_ids} rows with blank case_id will be rejected (kept in rejected log)")
    if blank_h_case_ids:
        rep.warnings.append(f"hearings: {blank_h_case_ids} rows with blank case_id will be rejected (kept in rejected log)")

    for col in ("court_id", "case_type"):
        n = int(_blank(c[col]).sum())
        rep.stats[f"cases_blank_{col}"] = n
        if n:
            rep.warnings.append(f"cases: {n} rows with blank {col} (kept as UNKNOWN; such cases have no peer group)")

    dup_cases = int(c["case_id"].dropna().duplicated().sum())
    rep.stats["cases_duplicate_ids"] = dup_cases
    if dup_cases:
        rep.warnings.append(f"cases: {dup_cases} duplicate case_id rows (first occurrence kept)")

    known = set(c["case_id"].dropna())
    orphans = int((~h["case_id"].isin(known) & ~_blank(h["case_id"])).sum())
    rep.stats["hearings_orphaned"] = orphans
    if orphans:
        rep.warnings.append(f"hearings: {orphans} rows reference case_ids absent from the cases table")
    if len(h) and orphans == len(h):
        rep.errors.append("hearings: no hearing references a case in the cases table (wrong files or mapping?)")

    if not len(h):
        rep.warnings.append("No per-hearing records: case-level analysis only (adjournment metrics unavailable).")
        return rep
    blank_dates = int(_blank(h["hearing_date"]).sum())
    rep.stats["hearings_blank_date"] = blank_dates
    if blank_dates:
        rep.warnings.append(f"hearings: {blank_dates} rows with blank hearing_date (kept, excluded from interval metrics)")
    text_cols = ["last_action", "last_order"]
    no_text = int(pd.concat([_blank(h[col]) for col in text_cols], axis=1).all(axis=1).sum())
    rep.stats["hearings_no_description"] = no_text
    if no_text:
        rep.warnings.append(f"hearings: {no_text} rows without action/order text (classified UNKNOWN, never as adjournment)")
    return rep


def assert_valid(raw: RawDataset) -> ValidationReport:
    rep = validate_raw(raw)
    if not rep.ok:
        raise IngestionError("Validation failed: " + "; ".join(rep.errors))
    return rep
