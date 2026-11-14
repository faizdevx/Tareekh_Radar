"""Adapter for the Development Data Lab (DDL) eCourts case data, 2010-2018.

Source: Harvard Dataverse, doi:10.7910/DVN/GHLGSW ("cases_clean_<year>" files and
keys/), released with Ash et al., "In-Group Bias in the Indian Judiciary" (REStat 2025).
Dataverse licence at download time: CC0 1.0. DDL's own site states CC BY-NC-SA 4.0 for
its public judicial data - cite the paper and use non-commercially to satisfy both.

Granularity: ONE ROW PER CASE. The release has filing, decision, first/last/next listing
dates, the purpose of the latest listing, case type and disposal nature. It does NOT
contain per-hearing histories, so adjournment counts/streaks cannot be computed from it.

Privacy: the source files contain party and advocate names and eCourts CNR numbers.
This adapter never reads those columns (see READ_COLUMNS) and never writes them.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from ..categories import assign_categories

log = logging.getLogger(__name__)

DATAVERSE_DOI = "doi:10.7910/DVN/GHLGSW"

# Only these columns are read from the source file.
READ_COLUMNS = [
    "ddl_case_id", "year", "state", "state_name", "district", "district_name", "court", "court_name",
    "date_of_filing", "date_of_decision", "date_first_list", "date_last_list", "date_next_list",
    "purpose_name", "type_name", "disp_name", "criminal", "act", "section",
]
EXCLUDED_SENSITIVE = ["pet_name", "def_name", "pet_adv", "def_adv", "cino", "case_no",
                      "*_muslim", "*_female", "ddl_*_judge_id", "judge_desg", "judge_position"]


# Every column is written as text (dates are parsed during cleaning).
_SCHEMA = pa.schema([(c, pa.string()) for c in (
    "case_id",
    "court_id",
    "court_name",
    "case_type",
    "filing_date",
    "disposal_date",
    "case_status",
    "source_reference",
    "first_listing_date",
    "last_listing_date",
    "next_listing_date",
    "current_purpose",
    "disposal_nature",
    "case_category",
    "act",
    "section",
    "filing_year",
    "state_code",
    "state_name",
    "district_id",
    "district_name",
)])


def _load_key(path: Path, code_col: str, name_col: str) -> pd.Series:
    """Lookup Series indexed by (year, code) -> decoded string."""
    key = pd.read_stata(path, convert_categoricals=False).dropna(subset=[code_col])
    idx = pd.MultiIndex.from_arrays([key["year"].astype("int64"), key[code_col].astype("int64")])
    vals = key[name_col].astype(object).map(lambda v: None if pd.isna(v) or not str(v).strip() else str(v).strip())
    s = pd.Series(vals.to_numpy(), index=idx)
    return s[~s.index.duplicated()]


def _decode(codes: pd.Series, years: pd.Series, key: pd.Series) -> pd.Series:
    ok = codes.notna()
    out = pd.Series([None] * len(codes), index=codes.index, dtype=object)
    if ok.any():
        idx = pd.MultiIndex.from_arrays([years[ok].astype("int64"), codes[ok].astype("int64")])
        out[ok] = key.reindex(idx).to_numpy()
    return out


def extract(
    dta_path: str | Path,
    keys_dir: str | Path,
    out_dir: str | Path,
    states: list[str] | None = None,
    districts: list[str] | None = None,
    chunksize: int = 400_000,
    name: str | None = None,
) -> dict[str, Path]:
    """Stream a cases_clean_<year>.dta file into a contract-shaped cases.parquet + mapping.yaml.

    states: 2-digit eCourts state codes (e.g. ["01"]); districts: "SS-DD" codes.
    """
    dta_path, keys_dir, out_dir = Path(dta_path), Path(keys_dir), Path(out_dir)
    if not dta_path.exists():
        raise FileNotFoundError(f"DDL file not found: {dta_path} (download instructions: docs/data_acquisition.md)")
    keys = {
        "purpose_name": _load_key(keys_dir / "purpose_name_key.tab", "purpose_name", "purpose_name_s"),
        "type_name": _load_key(keys_dir / "type_name_key.tab", "type_name", "type_name_s"),
        "disp_name": _load_key(keys_dir / "disp_name_key.tab", "disp_name", "disp_name_s"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_path = out_dir / "cases.parquet"
    tmp_path = out_dir / "cases.parquet.partial"
    writer = None
    n_read = n_kept = 0
    names: set[str] = set()
    reader = pd.read_stata(dta_path, columns=READ_COLUMNS, convert_categoricals=False,
                           convert_dates=False, chunksize=chunksize)
    with reader:
        for chunk in reader:
            n_read += len(chunk)
            st = chunk["state"].astype(str).str.zfill(2)
            dist = st + "-" + chunk["district"].astype(str).str.zfill(2)
            keep = pd.Series(True, index=chunk.index)
            if states:
                keep &= st.isin(states)
            if districts:
                keep &= dist.isin(districts)
            c = chunk[keep]
            if c.empty:
                continue
            st, dist = st[keep], dist[keep]
            yrs = c["year"]
            disposal_nature = _decode(c["disp_name"], yrs, keys["disp_name"])
            # DDL codes missing dispositions as the literal "disposition var missing".
            disposal_nature = disposal_nature.where(disposal_nature != "disposition var missing", None)
            df = pd.DataFrame({
                "case_id": c["ddl_case_id"].astype(str),
                "court_id": dist + "-" + c["court"].astype(str).str.zfill(2),
                "court_name": c["court_name"].astype(str).str.strip(),
                "case_type": _decode(c["type_name"], yrs, keys["type_name"]),
                "filing_date": c["date_of_filing"],
                "disposal_date": c["date_of_decision"],
                "case_status": None,  # derived from disposal_date during cleaning
                "source_reference": [f"ddl:{DATAVERSE_DOI}/{dta_path.stem}#ddl_case_id={i}" for i in c["ddl_case_id"]],
                "first_listing_date": c["date_first_list"],
                "last_listing_date": c["date_last_list"],
                "next_listing_date": c["date_next_list"],
                "current_purpose": _decode(c["purpose_name"], yrs, keys["purpose_name"]),
                "disposal_nature": disposal_nature,
                # DDL's `criminal` flag marks only a subset of criminal cases (0 is not "civil"),
                # so the category comes from the recorded type name and act/section instead.
                "case_category": assign_categories(_decode(c["type_name"], yrs, keys["type_name"]),
                                                   c["act"].astype(str).str.strip(),
                                                   c["section"].astype(str).str.strip()).to_numpy(),
                "act": c["act"].astype(str).str.strip(),
                "section": c["section"].astype(str).str.strip(),
                "filing_year": yrs.astype(int).astype(str),
                "state_code": st,
                "state_name": c["state_name"].astype(str).str.strip(),
                "district_id": dist,
                "district_name": c["district_name"].astype(str).str.strip(),
            })
            for col in df.columns:
                v = df[col].astype(object)
                txt = v.astype(str).str.strip()
                df[col] = txt.where(v.notna() & ~txt.isin(["", "nan", "NaT", "None"]), None).astype(object)
            # Stream each chunk to disk: a full-year file (e.g. 2018, ~12 GB .dta) does not fit in memory.
            table = pa.Table.from_pandas(df, schema=_SCHEMA, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(tmp_path, _SCHEMA)
            writer.write_table(table)
            n_kept += len(df)
            names.update(df["state_name"].dropna().unique().tolist())
            log.info("read %d rows, kept %d so far", n_read, n_kept)
    if writer is None:
        raise ValueError(f"No rows matched the filters (states={states}, districts={districts})")
    writer.close()
    tmp_path.replace(cases_path)
    scope = []
    if states:
        scope.append("states=" + ",".join(states))
    if districts:
        scope.append("districts=" + ",".join(districts))
    names = sorted(names)
    mapping = {
        "dataset": {
            "name": name or f"ddl_{dta_path.stem.replace('cases_clean_', '')}" + ("_" + "_".join(states) if states else ""),
            "is_synthetic": False,
            "level": "case",
            "source": f"Development Data Lab eCourts case data, Harvard Dataverse {DATAVERSE_DOI}, file {dta_path.name}",
            "license": "Dataverse: CC0 1.0. DDL site: CC BY-NC-SA 4.0 (non-commercial; cite Ash et al. REStat 2025).",
            "geographic_scope": "; ".join(scope) + (" | " if scope else "") + "states: " + ", ".join(names),
            "access_notes": ("Real district-court case records (one row per case) from eCourts via DDL; de-identified "
                             "by DDL. No per-hearing histories. Party/advocate names and CNR not read. "
                             f"Rows read: {n_read}; rows kept: {n_kept}."),
        },
        "cases": {},
    }
    mapping_path = out_dir / "mapping.yaml"
    mapping_path.write_text(yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"cases": cases_path, "mapping": mapping_path}
