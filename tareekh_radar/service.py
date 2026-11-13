"""Read-side service shared by the API and the Streamlit app.

All numbers are computed from the stored tables of a processed dataset; nothing is
hard-coded. Each result keeps its link to the source record (source_reference).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .anomaly import build_explanation, mode_config
from .storage import dataset_dir, list_datasets, load_json, load_table


class DatasetNotFound(KeyError):
    pass


@dataclass
class DatasetView:
    name: str
    cfg: dict
    manifest: dict
    run_info: dict
    quality: dict
    cases: pd.DataFrame
    hearings: pd.DataFrame
    anomalies: pd.DataFrame

    @property
    def mode(self) -> str:
        return self.run_info.get("data_level", "hearing")

    # ------------------------------------------------------------ overview
    def overview(self) -> dict[str, Any]:
        a, h = self.anomalies, self.hearings
        scored = a["score_status"] == "scored"
        out: dict[str, Any] = {
            "dataset": self.name,
            "data_level": self.mode,
            "is_synthetic": bool(self.manifest.get("is_synthetic", False)),
            "source": self.manifest.get("source"),
            "license": self.manifest.get("license"),
            "geographic_scope": self.manifest.get("geographic_scope"),
            "reference_date": self.run_info.get("reference_date"),
            "total_cases": int(len(a)),
            "total_hearings": int(len(h)),
            "courts": int(a["court_id"].nunique()),
            "case_status": a["case_status"].value_counts().to_dict(),
            "eligible_cases": int(a["eligible"].fillna(False).astype(bool).sum()),
            "scored_cases": int(scored.sum()),
            "flagged_cases": int(a["flagged"].sum()),
            "flagged_with_quality_issue": int(a.get("flag_has_quality_issue", pd.Series(False)).sum()),
            "severity": a.loc[a["flagged"], "severity"].value_counts().to_dict(),
            "mean_data_completeness": _r(a["data_completeness"].mean()),
        }
        if self.mode == "hearing" and len(h):
            ec = h["event_class"].value_counts()
            out.update({
                "confirmed_adjournments": int(ec.get("ADJOURNMENT", 0)),
                "procedural_progress_events": int(ec.get("PROCEDURAL_PROGRESS", 0)),
                "substantive_progress_events": int(ec.get("SUBSTANTIVE_PROGRESS", 0)),
                "unknown_events": int(ec.get("UNKNOWN", 0)),
                "unknown_record_pct": _r(100 * ec.get("UNKNOWN", 0) / len(h)),
                "median_adjournment_rate": _r(a["adjournment_rate"].median()),
            })
        else:
            out.update({
                "median_case_age_days_disposed": _r(a.loc[a["case_status"] == "DISPOSED", "case_age_days"].median()),
                "median_case_age_days_pending": _r(a.loc[a["case_status"] == "PENDING", "case_age_days"].median()),
                "median_days_since_last_listing_pending": _r(a["days_since_last_listing"].median()),
                "median_days_to_first_listing": _r(a["days_to_first_listing"].median()),
            })
        return out

    # ------------------------------------------------------------ anomalies
    def anomaly_table(self, court_id: str | None = None, case_type: str | None = None, stage: str | None = None,
                      severity: list[str] | None = None, min_completeness: float | None = None,
                      flagged_only: bool = True, exclude_quality_issues: bool = False,
                      limit: int | None = 200, offset: int = 0) -> pd.DataFrame:
        a = self.anomalies
        m = pd.Series(True, index=a.index)
        if flagged_only:
            m &= a["flagged"]
        if court_id:
            m &= a["court_id"] == court_id
        if case_type:
            m &= a["case_type"] == case_type
        if stage:
            m &= a["current_stage"] == stage
        if severity:
            m &= a["severity"].isin(severity)
        if min_completeness is not None:
            m &= a["data_completeness"].fillna(0) >= min_completeness
        if exclude_quality_issues and "flag_has_quality_issue" in a:
            m &= ~a["flag_has_quality_issue"].astype(bool)
        cols = ["case_id", "court_id", "court_name", "case_type", "case_status", "current_stage", "anomaly_score",
                "anomaly_percentile", "severity", "contributing_features", "peer_group_size", "data_completeness",
                "flag_has_quality_issue", "if_score", "if_flag", "anomaly_explanation"]
        out = a.loc[m, [c for c in cols if c in a.columns]].sort_values("anomaly_score", ascending=False)
        if limit is not None:
            out = out.iloc[offset: offset + limit]
        return out

    def case_row(self, case_id: str) -> pd.Series:
        hit = self.anomalies[self.anomalies["case_id"] == case_id]
        if hit.empty:
            raise KeyError(case_id)
        return hit.iloc[0]

    def explanation(self, case_id: str) -> dict[str, Any]:
        row = self.case_row(case_id)
        stored = row.get("anomaly_explanation_json")
        if isinstance(stored, str) and stored:
            return json.loads(stored)
        fspec = mode_config(self.cfg, self.mode)["features"]
        return json.loads(json.dumps(build_explanation(row, fspec, self.mode), default=str))

    def timeline(self, case_id: str) -> pd.DataFrame:
        """Chronological record: hearings (hearing mode) or recorded case dates (case mode)."""
        if self.mode == "hearing" and len(self.hearings):
            h = self.hearings[self.hearings["case_id"] == case_id].sort_values(["hearing_date", "source_row"])
            cols = ["hearing_id", "hearing_date", "hearing_stage_raw", "stage_norm", "event_class", "event_confidence",
                    "event_method", "event_reason", "last_action", "last_order", "next_hearing_purpose",
                    "data_quality_status", "source_reference"]
            out = h[[c for c in cols if c in h.columns]].copy()
            d = pd.to_datetime(out["hearing_date"])
            out["days_since_previous"] = d.diff().dt.days
            return out.reset_index(drop=True)
        c = self.cases[self.cases["case_id"] == case_id]
        if c.empty:
            raise KeyError(case_id)
        r = c.iloc[0]
        events = [
            ("Filed", "filing_date", None),
            ("First listed", "first_listing_date", None),
            ("Last listed", "last_listing_date", r.get("current_purpose")),
            ("Next listing scheduled", "next_listing_date", None),
            ("Decided", "disposal_date", r.get("disposal_nature")),
        ]
        rows = []
        for label, col, detail in events:
            if col not in c.columns:
                continue
            rows.append({"event": label, "date": r.get(col), "detail": detail,
                         "date_status": r.get(f"{col}_status"), "raw_value": r.get(f"{col}_raw"),
                         "source_reference": r.get("source_reference")})
        out = pd.DataFrame(rows)
        out["date"] = pd.to_datetime(out["date"])
        known = out.dropna(subset=["date"]).sort_values("date")
        out = pd.concat([known, out[out["date"].isna()]])
        out["days_since_previous"] = out["date"].diff().dt.days
        return out.reset_index(drop=True)


def _r(v, nd: int = 2):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v) else round(float(v), nd)


_CACHE: dict[tuple, DatasetView] = {}


def get_dataset(cfg: dict, name: str) -> DatasetView:
    """Load a processed dataset (cached until its files change)."""
    if name not in list_datasets(cfg):
        raise DatasetNotFound(name)
    p = dataset_dir(cfg, name) / "anomalies.parquet"
    key = (str(dataset_dir(cfg, name)), p.stat().st_mtime)
    if key not in _CACHE:
        if len(_CACHE) >= 4:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = DatasetView(
            name=name, cfg=cfg,
            manifest=load_json(cfg, name, "manifest"),
            run_info=load_json(cfg, name, "run_info"),
            quality=load_json(cfg, name, "quality_report"),
            cases=load_table(cfg, name, "cases"),
            hearings=load_table(cfg, name, "hearings"),
            anomalies=load_table(cfg, name, "anomalies"),
        )
    return _CACHE[key]


def optional_json(cfg: dict, name: str, key: str) -> dict | None:
    try:
        return load_json(cfg, name, key)
    except FileNotFoundError:
        return None


def optional_csv(cfg: dict, name: str, fname: str) -> pd.DataFrame | None:
    p = dataset_dir(cfg, name) / fname
    return pd.read_csv(p) if p.exists() else None
