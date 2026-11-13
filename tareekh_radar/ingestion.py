"""Load case and hearing tables from CSV / Excel / JSON / Parquet with provenance.

Raw values are read as strings so that nothing (dates, ids with leading zeros) is
silently coerced. Source columns are mapped onto the data contract in schemas.py.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .schemas import CASES, HEARINGS, TableSchema

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet"}


class IngestionError(ValueError):
    """Raised when input data cannot be loaded or does not meet the data contract."""


@dataclass
class DatasetManifest:
    name: str
    is_synthetic: bool
    source: str = ""
    license: str = ""
    geographic_scope: str = ""
    level: str = "hearing"
    access_notes: str = ""
    files: list[dict[str, Any]] = field(default_factory=list)
    dropped_columns: dict[str, list[str]] = field(default_factory=dict)
    generated_hearing_ids: int = 0
    loaded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DatasetManifest":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class RawDataset:
    cases: pd.DataFrame
    hearings: pd.DataFrame
    manifest: DatasetManifest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a tabular file with all values as strings."""
    p = Path(path)
    if not p.exists():
        raise IngestionError(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestionError(f"Unsupported file type {suffix!r}; expected one of {sorted(SUPPORTED_SUFFIXES)}")
    try:
        if suffix == ".csv":
            df = pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")
        elif suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(p, dtype=str, keep_default_na=False, na_values=[""])
        elif suffix == ".jsonl":
            df = pd.read_json(p, lines=True, dtype=False)
        elif suffix == ".json":
            with open(p, encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                # Accept {"records": [...]} or {"data": [...]}
                for key in ("records", "data", "rows"):
                    if isinstance(payload.get(key), list):
                        payload = payload[key]
                        break
            if not isinstance(payload, list):
                raise IngestionError(f"JSON file {p} must contain a list of records")
            df = pd.DataFrame.from_records(payload)
        else:
            df = pd.read_parquet(p)
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.strftime("%Y-%m-%d")
    except IngestionError:
        raise
    except Exception as exc:  # pragma: no cover - library-specific messages
        raise IngestionError(f"Could not read {p}: {exc}") from exc
    for col in df.columns:
        v = df[col].astype(object)
        df[col] = v.astype(str).where(v.notna(), None).astype(object)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_mapping(path: str | Path | None) -> dict[str, Any]:
    """Load a column-mapping YAML: {dataset: {...}, cases: {schema_col: source_col}, hearings: {...}}."""
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        raise IngestionError(f"Mapping file not found: {p}")
    with open(p, encoding="utf-8") as fh:
        mapping = yaml.safe_load(fh) or {}
    if not isinstance(mapping, dict):
        raise IngestionError("Mapping file must contain a mapping")
    return mapping


def apply_mapping(
    df: pd.DataFrame, schema: TableSchema, column_map: dict[str, str] | None, drop_unmapped: bool
) -> tuple[pd.DataFrame, list[str]]:
    """Rename source columns to contract names, add absent optional columns as nulls."""
    column_map = column_map or {}
    rename: dict[str, str] = {}
    lower_cols = {c.lower(): c for c in df.columns}
    for target in schema.names:
        source = column_map.get(target)
        if source is not None:
            if source not in df.columns:
                raise IngestionError(f"{schema.name}: mapped column {source!r} for {target!r} not in file")
            rename[source] = target
        elif target in df.columns:
            rename[target] = target
        elif target.lower() in lower_cols:
            rename[lower_cols[target.lower()]] = target
    out = df.rename(columns=rename)
    mapped = set(rename.values())
    missing_required = [c for c in schema.required if c not in mapped]
    if missing_required:
        raise IngestionError(
            f"{schema.name}: required columns missing: {missing_required}. "
            f"Available: {list(df.columns)}. Provide a mapping file (see config/mappings/)."
        )
    dropped = [c for c in out.columns if c not in schema.names]
    if drop_unmapped and dropped:
        out = out.drop(columns=dropped)
    for col in schema.names:
        if col not in out.columns:
            out[col] = None
    ordered = schema.names + ([c for c in out.columns if c not in schema.names] if not drop_unmapped else [])
    return out[ordered].copy(), dropped


def load_dataset(
    cases_path: str | Path,
    hearings_path: str | Path | None,
    mapping_path: str | Path | None = None,
    *,
    dataset_name: str | None = None,
    is_synthetic: bool | None = None,
    drop_unmapped: bool = True,
) -> RawDataset:
    """Load cases (and optional per-hearing) files into contract-shaped frames with provenance.

    hearings_path may be None for case-level sources (one row per case, e.g. DDL eCourts).
    """
    mapping = load_mapping(mapping_path)
    meta = mapping.get("dataset", {}) or {}
    cases_raw = read_table(cases_path)
    if cases_raw.empty:
        raise IngestionError(f"Cases file {cases_path} has no rows")
    cases, dropped_c = apply_mapping(cases_raw, CASES, mapping.get("cases"), drop_unmapped)
    cp = Path(cases_path)
    missing_ref = cases["source_reference"].isna()
    if missing_ref.any():
        cases.loc[missing_ref, "source_reference"] = [f"{cp.name}:row{i + 2}" for i in cases.index[missing_ref]]

    if hearings_path is not None:
        hearings_raw = read_table(hearings_path)
        if hearings_raw.empty:
            raise IngestionError(f"Hearings file {hearings_path} has no rows")
        hearings, dropped_h = apply_mapping(hearings_raw, HEARINGS, mapping.get("hearings"), drop_unmapped)
        hp = Path(hearings_path)
        miss = hearings["source_reference"].isna()
        if miss.any():
            hearings.loc[miss, "source_reference"] = [f"{hp.name}:row{i + 2}" for i in hearings.index[miss]]
    else:
        hearings = pd.DataFrame({c: pd.Series(dtype=object) for c in HEARINGS.names})
        dropped_h = []
    hearings["source_row"] = range(len(hearings))
    missing_ids = hearings["hearing_id"].isna()
    generated = int(missing_ids.sum())
    if generated:
        hearings.loc[missing_ids, "hearing_id"] = [
            f"{cid}#r{row}" for cid, row in zip(hearings.loc[missing_ids, "case_id"], hearings.loc[missing_ids, "source_row"])
        ]

    synthetic_flag = is_synthetic if is_synthetic is not None else bool(meta.get("is_synthetic", False))
    manifest = DatasetManifest(
        name=dataset_name or meta.get("name") or cp.parent.name or "dataset",
        is_synthetic=synthetic_flag,
        source=str(meta.get("source", "")),
        license=str(meta.get("license", "")),
        geographic_scope=str(meta.get("geographic_scope", "")),
        access_notes=str(meta.get("access_notes", "")),
        files=[{"role": "cases", "path": str(cp), "sha256": _sha256(cp), "rows": len(cases_raw)}]
        + ([{"role": "hearings", "path": str(hp), "sha256": _sha256(hp), "rows": len(hearings)}]
           if hearings_path is not None else []),
        level=str(meta.get("level", "hearing" if hearings_path is not None else "case")),
        dropped_columns={"cases": dropped_c if drop_unmapped else [], "hearings": dropped_h if drop_unmapped else []},
        generated_hearing_ids=generated,
    )
    return RawDataset(cases=cases, hearings=hearings, manifest=manifest)
