"""End-to-end processing: load -> validate -> clean -> pseudonymize -> classify -> features -> anomalies -> store."""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import DISCLAIMER, __version__
from .anomaly import run_anomaly_detection
from .classification import MLClassifier, classify_hearings, decision_log, load_human_labels
from .cleaning import clean_dataset
from .config import config_hash, resolve_path
from .features import compute_case_features
from .ingestion import RawDataset, load_dataset
from .privacy import apply_pseudonyms, build_id_map
from .storage import write_tables
from .validation import assert_valid

log = logging.getLogger(__name__)
MODEL_FILENAME = "event_classifier.joblib"


@dataclass
class ProcessedDataset:
    tables: dict[str, pd.DataFrame]
    meta: dict[str, Any]
    id_map: pd.DataFrame | None


def default_model_path(cfg: dict) -> Path:
    return resolve_path(cfg, "models_dir") / MODEL_FILENAME


def process(
    raw: RawDataset,
    cfg: dict,
    ml: MLClassifier | None = None,
    human_labels: pd.DataFrame | None = None,
    salt: bytes | None = None,
) -> ProcessedDataset:
    validation = assert_valid(raw)
    clean = clean_dataset(raw, cfg)
    cases, hearings, rejected, duplicates = clean.cases, clean.hearings, clean.rejected, clean.duplicates

    id_map = None
    if cfg["privacy"].get("pseudonymize", True):
        all_ids = pd.concat([cases["case_id"], hearings["case_id"]], ignore_index=True)
        id_map = build_id_map(all_ids, cfg, salt)
        cases = apply_pseudonyms(cases, id_map)
        hearings = apply_pseudonyms(hearings, id_map)
        if "case_id" in rejected.columns:
            rejected = apply_pseudonyms(rejected, id_map)
        if "case_id" in duplicates.columns:
            duplicates = apply_pseudonyms(duplicates, id_map)

    level = clean.level
    if level == "hearing":
        classified = classify_hearings(hearings, cfg, ml=ml, human_labels=human_labels)
    else:
        classified = hearings.copy()
        for c in ["event_class", "event_confidence", "event_method", "event_rule_id", "event_subtype",
                  "event_reason", "rule_class", "ml_class", "ml_probability"]:
            classified[c] = pd.Series(dtype=object)
    features = compute_case_features(cases, classified, cfg)
    anomalies = run_anomaly_detection(features, cfg, level)

    quality = dict(clean.quality)
    n_h = len(classified)
    unk = classified["event_class"] == "UNKNOWN"
    min_rates = cfg["features"]["min_hearings_for_rates"]
    quality["classification"] = {"applicable": False, "note": "No per-hearing records in this source."} if level == "case" else {
        "class_distribution": classified["event_class"].value_counts().to_dict(),
        "method_distribution": classified["event_method"].value_counts().to_dict(),
        "unknown_event_pct": round(100 * unk.mean(), 2) if n_h else None,
        "unknown_reason_counts": classified.loc[unk, "event_reason"].fillna("").str.split(":").str[0].value_counts().to_dict(),
        "mean_confidence_known": round(float(classified.loc[~unk, "event_confidence"].mean()), 3) if (~unk).any() else None,
        "low_confidence_known_pct": round(100 * float((classified.loc[~unk, "event_confidence"] < 0.8).mean()), 2) if (~unk).any() else None,
    }
    n_c = len(features)
    quality["case_coverage"] = {
        "cases": n_c,
        "cases_with_no_hearings": int((features["total_hearings"] == 0).sum()),
        "cases_with_sufficient_history_pct": (round(100 * float((features["dated_hearings"] >= min_rates).mean()), 2)
                                              if level == "hearing" else
                                              round(100 * float(features["last_listing_date"].notna().mean()), 2)) if n_c else None,
        "sufficient_history_definition": (f">= {min_rates} dated hearings" if level == "hearing"
                                          else "valid last-listing date recorded"),
        "cases_eligible_for_anomaly_analysis_pct": round(100 * float(features["eligible"].fillna(False).mean()), 2) if n_c else None,
        "cases_scored_pct": round(100 * float((anomalies["score_status"] == "scored").mean()), 2) if n_c else None,
        "cases_without_peer_group": int((anomalies["score_status"] == "no_comparable_peer_group").sum()),
        "ineligible_reasons": features["ineligible_reason"].dropna().str.split(";").explode().value_counts().to_dict(),
    }
    quality["validation"] = validation.to_dict()

    ref_date = features.attrs.get("reference_date")
    meta = {
        "manifest": raw.manifest.to_dict(),
        "quality_report": quality,
        "run_info": {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "tareekh_radar_version": __version__,
            "python": platform.python_version(),
            "config_hash": config_hash(cfg),
            "data_level": level,
            "classification_mode": ("not_applicable" if level == "case" else
                                    cfg["classification"]["mode"] if ml is not None else "rules"),
            "ml_model_used": ml is not None,
            "ml_trained_on": getattr(ml, "trained_on", None) if ml is not None else None,
            "human_labels_applied": int(len(human_labels)) if human_labels is not None else 0,
            "reference_date": ref_date,
            "pseudonymized": id_map is not None,
            "disclaimer": DISCLAIMER,
        },
        "config": cfg,
    }
    tables = {
        "cases": cases,
        "hearings": classified,
        "features": features,
        "anomalies": anomalies,
        "rejected": rejected,
        "duplicates": duplicates,
        "decision_log": decision_log(classified),
    }
    return ProcessedDataset(tables=tables, meta=meta, id_map=id_map)


def run_pipeline(
    cases_path: str | Path,
    hearings_path: str | Path | None,
    cfg: dict,
    mapping_path: str | Path | None = None,
    dataset_name: str | None = None,
    is_synthetic: bool | None = None,
    model_path: str | Path | None = None,
    human_labels_path: str | Path | None = None,
) -> tuple[Path, ProcessedDataset]:
    raw = load_dataset(cases_path, hearings_path, mapping_path, dataset_name=dataset_name,
                       is_synthetic=is_synthetic, drop_unmapped=cfg["privacy"].get("drop_unmapped_columns", True))
    ml = None
    if hearings_path is not None and cfg["classification"]["mode"] != "rules":
        mp = Path(model_path) if model_path else default_model_path(cfg)
        if mp.exists():
            ml = MLClassifier.load(mp, cfg["classification"])
            log.info("Loaded ML classifier from %s", mp)
        else:
            log.info("No ML model at %s; using rule classifier only", mp)
    labels = load_human_labels(human_labels_path) if human_labels_path else None
    result = process(raw, cfg, ml=ml, human_labels=labels)
    out = write_tables(cfg, raw.manifest.name, result.tables, result.meta)
    if result.id_map is not None:
        # Re-identification key: local only (data/processed is gitignored). Do not share.
        result.id_map.to_parquet(out / "id_map.LOCAL_ONLY.parquet", index=False)
    return out, result


def summarize(result: ProcessedDataset) -> dict[str, Any]:
    a = result.tables["anomalies"]
    h = result.tables["hearings"]
    return {
        "cases": int(len(a)),
        "hearings": int(len(h)),
        "scored_cases": int((a["score_status"] == "scored").sum()),
        "flagged_cases": int(a["flagged"].sum()),
        "severity": a.loc[a["flagged"], "severity"].value_counts().to_dict(),
        "unknown_event_pct": result.meta["quality_report"]["classification"].get("unknown_event_pct"),
        "data_level": result.meta["run_info"]["data_level"],
    }


def _np_default(o):  # pragma: no cover
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return str(o)
