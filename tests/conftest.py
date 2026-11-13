"""Shared test helpers.

All inputs here are small hand-written unit-test fixtures that exercise code paths.
They live only in tests/ and are never written to data/ or shown in the app.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tareekh_radar.config import load_config
from tareekh_radar.ingestion import DatasetManifest, RawDataset
from tareekh_radar.schemas import CASES, HEARINGS


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch) -> dict:
    monkeypatch.setenv("TAREEKH_SALT", "unit-test-salt")
    paths = {k: str(tmp_path / k) for k in ("raw_dir", "processed_dir", "annotations_dir", "models_dir", "runs_dir")}
    paths["salt_file"] = str(tmp_path / ".salt")
    c = load_config(overrides={"paths": paths})
    c["dates"]["max_valid_date"] = "2030-01-01"
    return c


def make_cases(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in CASES.names:
        if col not in df.columns:
            df[col] = None
    return df.astype(object).where(df.notna(), None)


def make_hearings(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in HEARINGS.names:
        if col not in df.columns:
            df[col] = None
    df["source_row"] = range(len(df))
    return df.astype(object).where(df.notna(), None)


def raw(cases: pd.DataFrame, hearings: pd.DataFrame | None = None) -> RawDataset:
    if hearings is None:
        hearings = pd.DataFrame({c: pd.Series(dtype=object) for c in HEARINGS.names})
    return RawDataset(cases=cases, hearings=hearings, manifest=DatasetManifest(name="unit", is_synthetic=False))


def hearing_series(case_id: str, start: str, texts: list[str | None], stages: list[str | None] | None = None,
                   step_days: int = 30) -> list[dict]:
    d0 = pd.Timestamp(start)
    stages = stages or ["Evidence"] * len(texts)
    return [{"hearing_id": f"{case_id}-{i}", "case_id": case_id,
             "hearing_date": (d0 + pd.Timedelta(days=step_days * i)).strftime("%d-%m-%Y"),
             "hearing_stage": st, "last_order": t} for i, (t, st) in enumerate(zip(texts, stages))]


def case_level_population(n_per_group: int = 40, seed: int = 0, outlier: bool = True) -> pd.DataFrame:
    """Deterministic case-level test population: 2 courts x 2 types, pending and disposed."""
    rng = np.random.default_rng(seed)
    rows = []
    k = 0
    for court in ("01-01-01", "01-01-02"):
        for ctype in ("CC", "OS"):
            for status in ("pending", "disposed"):
                for _ in range(n_per_group):
                    k += 1
                    filing = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
                    first = filing + pd.Timedelta(days=int(rng.integers(1, 30)))
                    last = pd.Timestamp("2020-06-01") - pd.Timedelta(days=int(rng.integers(5, 60)))
                    nxt = last + pd.Timedelta(days=int(rng.integers(20, 60)))
                    dec = filing + pd.Timedelta(days=int(rng.integers(200, 900)))
                    rows.append({
                        "case_id": f"T{k:05d}", "court_id": court, "court_name": f"Court {court}", "case_type": ctype,
                        "filing_date": filing.strftime("%Y-%m-%d"),
                        "disposal_date": dec.strftime("%Y-%m-%d") if status == "disposed" else None,
                        "first_listing_date": first.strftime("%Y-%m-%d"),
                        "last_listing_date": (min(last, dec) if status == "disposed" else last).strftime("%Y-%m-%d"),
                        "next_listing_date": None if status == "disposed" else nxt.strftime("%Y-%m-%d"),
                        "current_purpose": "evidence", "case_category": "CRIMINAL" if ctype == "CC" else "CIVIL",
                        "state_code": "01", "district_id": "01-01",
                    })
    if outlier:
        # one pending case not listed for ~6 years
        rows.append({**rows[0], "case_id": "OUTLIER", "last_listing_date": "2014-05-01", "next_listing_date": "2014-06-01"})
    return make_cases(rows)
