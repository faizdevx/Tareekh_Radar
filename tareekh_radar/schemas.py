"""Data contracts for cases, hearings and analysis results.

These definitions are the single source of truth for column names, required fields
and types. Ingestion maps source columns onto them; every downstream module relies
on them. Fields a source does not provide are kept as nulls - never invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str  # "string" | "date" | "int" | "float" | "bool"
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...] = field(default_factory=tuple)

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def required(self) -> list[str]:
        return [c.name for c in self.columns if c.required]

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(name)


CASES = TableSchema(
    name="cases",
    primary_key=("case_id",),
    columns=(
        Column("case_id", "string", True, "Source case identifier (CNR or equivalent). Pseudonymized in outputs."),
        Column("court_id", "string", True, "Court/establishment code from the source."),
        Column("court_name", "string", False, "Court/establishment name."),
        Column("case_type", "string", True, "Case type as recorded; normalized during cleaning."),
        Column("filing_date", "date", False, "Filing/registration date."),
        Column("disposal_date", "date", False, "Disposal/decision date, if disposed."),
        Column("case_status", "string", False, "Pending/Disposed or source status text."),
        Column("source_reference", "string", False, "Provenance pointer (file, URL, record id)."),
        # Optional case-level listing fields (present in case-level sources such as DDL eCourts).
        Column("first_listing_date", "date", False, "Date the case was first listed before a court."),
        Column("last_listing_date", "date", False, "Most recent recorded listing date."),
        Column("next_listing_date", "date", False, "Next scheduled listing date at the data snapshot."),
        Column("current_purpose", "string", False, "Purpose/stage of the latest listing as recorded."),
        Column("disposal_nature", "string", False, "Nature of disposal as recorded (e.g. acquitted, dismissed)."),
        Column("case_category", "string", False, "Coarse category from the source (e.g. criminal/civil)."),
        Column("state_code", "string", False, "State code from the source."),
        Column("state_name", "string", False, "State name."),
        Column("district_id", "string", False, "State+district code from the source."),
        Column("district_name", "string", False, "District name."),
    ),
)

CASE_LISTING_DATE_COLUMNS = ["first_listing_date", "last_listing_date", "next_listing_date"]

HEARINGS = TableSchema(
    name="hearings",
    primary_key=("hearing_id",),
    columns=(
        Column("hearing_id", "string", False, "Source hearing id; generated from case_id+row when absent."),
        Column("case_id", "string", True, "Foreign key to cases.case_id."),
        Column("hearing_date", "date", True, "Date of the listing/business."),
        Column("hearing_stage", "string", False, "Stage of case at this hearing (e.g. Evidence)."),
        Column("last_action", "string", False, "Business recorded on the date."),
        Column("last_order", "string", False, "Order/proceeding text recorded on the date."),
        Column("next_hearing_purpose", "string", False, "Purpose of the NEXT listing (not used for classification)."),
        Column("source_reference", "string", False, "Provenance pointer."),
        Column("data_quality_status", "string", False, "Quality flags; filled by cleaning."),
    ),
)

# Columns produced by the classifier and attached to hearings.
CLASSIFICATION_COLUMNS = [
    "event_class",
    "event_confidence",
    "event_method",
    "event_rule_id",
    "event_subtype",
    "event_reason",
]

ANALYSIS_RESULTS = TableSchema(
    name="analysis_results",
    primary_key=("case_id",),
    columns=(
        Column("case_id", "string", True),
        Column("total_hearings", "int"),
        Column("confirmed_adjournments", "int"),
        Column("procedural_progress_events", "int"),
        Column("substantive_progress_events", "int"),
        Column("unknown_events", "int"),
        Column("adjournment_rate", "float"),
        Column("non_progress_streak", "int"),
        Column("repeated_stage_count", "int"),
        Column("median_hearing_interval", "float"),
        Column("maximum_hearing_gap", "float"),
        Column("unknown_record_percentage", "float"),
        Column("anomaly_score", "float"),
        Column("anomaly_percentile", "float"),
        Column("anomaly_explanation", "string"),
    ),
)

EVENT_CLASSES = ("ADJOURNMENT", "PROCEDURAL_PROGRESS", "SUBSTANTIVE_PROGRESS", "UNKNOWN")
PROGRESS_CLASSES = ("PROCEDURAL_PROGRESS", "SUBSTANTIVE_PROGRESS")

# Hearing-level quality flags (pipe-separated in data_quality_status).
QF_OK = "ok"
QF_MISSING_DATE = "missing_date"
QF_INVALID_DATE = "invalid_date"
QF_OUT_OF_RANGE_DATE = "date_out_of_range"
QF_BEFORE_FILING = "before_filing_date"
QF_AFTER_DISPOSAL = "after_disposal_date"
QF_MISSING_TEXT = "missing_description"
QF_SAME_DATE = "multiple_entries_same_date"
QF_ORPHAN = "case_not_in_cases_table"
QF_SOURCE_ORDER = "source_order_not_chronological"
