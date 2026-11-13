"""FastAPI backend over processed datasets.

Run:  uvicorn tareekh_radar.api:app --reload
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from . import DISCLAIMER, __version__
from .classification import RuleClassifier
from .config import load_config
from .service import DatasetNotFound, get_dataset, optional_json
from .storage import list_datasets


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))


def _clean(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=lambda o: None if isinstance(o, float) and np.isnan(o) else str(o)))


class ClassifyRequest(BaseModel):
    text: str


def create_app(cfg: dict | None = None) -> FastAPI:
    cfg = cfg or load_config()
    app = FastAPI(title="Tareekh Radar API", version=__version__,
                  description="Statistical anomaly detection in court hearing records. " + DISCLAIMER)
    rules = RuleClassifier(cfg["classification"])

    def ds(name: str):
        try:
            return get_dataset(cfg, name)
        except DatasetNotFound:
            raise HTTPException(404, f"Dataset {name!r} not found. Available: {list_datasets(cfg)}")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "datasets": len(list_datasets(cfg))}

    @app.get("/datasets")
    def datasets() -> list[dict]:
        out = []
        for name in list_datasets(cfg):
            m = optional_json(cfg, name, "manifest") or {}
            r = optional_json(cfg, name, "run_info") or {}
            out.append({"name": name, "data_level": r.get("data_level"), "is_synthetic": m.get("is_synthetic"),
                        "source": m.get("source"), "geographic_scope": m.get("geographic_scope")})
        return out

    @app.get("/datasets/{name}/overview")
    def overview(name: str) -> dict:
        return _clean({**ds(name).overview(), "disclaimer": DISCLAIMER})

    @app.get("/datasets/{name}/quality")
    def quality(name: str) -> dict:
        return _clean(ds(name).quality)

    @app.get("/datasets/{name}/anomalies")
    def anomalies(name: str, court_id: str | None = None, case_type: str | None = None, stage: str | None = None,
                  severity: list[str] | None = Query(None), min_completeness: float | None = None,
                  exclude_quality_issues: bool = False, limit: int = Query(100, le=1000), offset: int = 0) -> dict:
        v = ds(name)
        t = v.anomaly_table(court_id, case_type, stage, severity, min_completeness, True, exclude_quality_issues,
                            limit, offset)
        return {"count": int(len(t)), "offset": offset, "items": _records(t), "disclaimer": DISCLAIMER}

    @app.get("/datasets/{name}/cases/{case_id}")
    def case(name: str, case_id: str) -> dict:
        v = ds(name)
        try:
            row = v.case_row(case_id)
        except KeyError:
            raise HTTPException(404, f"Case {case_id!r} not found")
        return _clean({"case": json.loads(row.to_json(date_format="iso", default_handler=str)),
                       "explanation": v.explanation(case_id)})

    @app.get("/datasets/{name}/cases/{case_id}/timeline")
    def timeline(name: str, case_id: str) -> dict:
        v = ds(name)
        try:
            t = v.timeline(case_id)
        except KeyError:
            raise HTTPException(404, f"Case {case_id!r} not found")
        return {"case_id": case_id, "data_level": v.mode, "events": _records(t)}

    @app.post("/classify")
    def classify(req: ClassifyRequest) -> dict:
        d = rules.classify_text(req.text)
        return {"event_class": d.event_class, "confidence": d.event_confidence, "method": d.event_method,
                "rule_id": d.event_rule_id, "subtype": d.event_subtype, "reason": d.event_reason}

    return app


app = create_app()
