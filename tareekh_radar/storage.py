"""Analytical storage: one Parquet file per table plus a DuckDB database per dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .config import resolve_path

TABLES = ["cases", "hearings", "features", "anomalies", "rejected", "duplicates", "decision_log"]


def dataset_dir(cfg: dict, name: str) -> Path:
    return resolve_path(cfg, "processed_dir") / name


def _parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].astype(object).map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else
                                    (v if isinstance(v, str) else json.dumps(v, default=str) if isinstance(v, (list, dict)) else str(v)))
    return out


def write_tables(cfg: dict, name: str, tables: dict[str, pd.DataFrame], meta: dict[str, Any]) -> Path:
    out = dataset_dir(cfg, name)
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / "tareekh.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        for tname, df in tables.items():
            safe = _parquet_safe(df)
            safe.to_parquet(out / f"{tname}.parquet", index=False)
            con.register("tmp_df", safe)
            con.execute(f"CREATE TABLE {tname} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")
    finally:
        con.close()
    for key, payload in meta.items():
        (out / f"{key}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def list_datasets(cfg: dict) -> list[str]:
    root = resolve_path(cfg, "processed_dir")
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "manifest.json").exists())


def load_table(cfg: dict, name: str, table: str) -> pd.DataFrame:
    path = dataset_dir(cfg, name) / f"{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Table {table!r} not found for dataset {name!r} ({path})")
    return pd.read_parquet(path)


def load_json(cfg: dict, name: str, key: str) -> dict:
    path = dataset_dir(cfg, name) / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"{key}.json not found for dataset {name!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def query(cfg: dict, name: str, sql: str, params: list | None = None) -> pd.DataFrame:
    """Read-only SQL against a dataset's DuckDB file."""
    db_path = dataset_dir(cfg, name) / "tareekh.duckdb"
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()
