import json

import pandas as pd
import pytest

from tareekh_radar.ingestion import IngestionError, load_dataset, read_table
from tareekh_radar.validation import assert_valid, validate_raw

from .conftest import make_cases, make_hearings, raw


def _write_pair(tmp_path, fmt="csv"):
    cases = pd.DataFrame({"CNR": ["A1", "A2"], "Court": ["C1", "C1"], "Type": ["O.S.", "OS"],
                          "PartyName": ["X", "Y"]})
    hearings = pd.DataFrame({"case_id": ["A1", "A1", "A2"], "hearing_date": ["01-02-2015", "01-03-2015", "05-05-2016"],
                             "last_order": ["Adjourned", "Evidence recorded", None]})
    cp, hp = tmp_path / f"c.{fmt}", tmp_path / f"h.{fmt}"
    if fmt == "csv":
        cases.to_csv(cp, index=False)
        hearings.to_csv(hp, index=False)
    elif fmt == "xlsx":
        cases.to_excel(cp, index=False)
        hearings.to_excel(hp, index=False)
    else:
        cp.write_text(json.dumps(cases.to_dict("records")))
        hp.write_text(json.dumps({"records": hearings.where(hearings.notna(), None).to_dict("records")}))
    mp = tmp_path / "map.yaml"
    mp.write_text("dataset: {name: t, source: unit}\ncases: {case_id: CNR, court_id: Court, case_type: Type}\n")
    return cp, hp, mp


@pytest.mark.parametrize("fmt", ["csv", "xlsx", "json"])
def test_load_formats_with_mapping_and_provenance(tmp_path, fmt):
    cp, hp, mp = _write_pair(tmp_path, fmt)
    ds = load_dataset(cp, hp, mp)
    assert list(ds.cases["case_id"]) == ["A1", "A2"]
    assert "PartyName" not in ds.cases.columns  # unmapped (possibly personal) columns dropped
    assert ds.manifest.dropped_columns["cases"] == ["PartyName"]
    assert ds.hearings["hearing_id"].notna().all()  # generated ids
    assert ds.manifest.generated_hearing_ids == 3
    assert all(len(f["sha256"]) == 64 for f in ds.manifest.files)
    assert ds.cases["source_reference"].str.contains("row").all()


def test_cases_only_dataset(tmp_path):
    cp, _, mp = _write_pair(tmp_path)
    ds = load_dataset(cp, None, mp)
    assert ds.hearings.empty and ds.manifest.level == "case"
    rep = validate_raw(ds)
    assert rep.ok and any("case-level" in w for w in rep.warnings)


def test_missing_required_column_raises(tmp_path):
    p = tmp_path / "c.csv"
    pd.DataFrame({"foo": [1]}).to_csv(p, index=False)
    h = tmp_path / "h.csv"
    pd.DataFrame({"case_id": ["1"], "hearing_date": ["01-01-2015"]}).to_csv(h, index=False)
    with pytest.raises(IngestionError, match="required columns missing"):
        load_dataset(p, h)


def test_unsupported_and_missing_files(tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("x")
    with pytest.raises(IngestionError, match="Unsupported"):
        read_table(bad)
    with pytest.raises(IngestionError, match="not found"):
        read_table(tmp_path / "nope.csv")


def test_empty_file_rejected(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("case_id,court_id,case_type\n")
    with pytest.raises(IngestionError, match="no rows"):
        load_dataset(p, None)


def test_validation_detects_orphans_and_blank_ids():
    c = make_cases([{"case_id": "A", "court_id": "1", "case_type": "x"}, {"case_id": None, "court_id": "1", "case_type": "x"}])
    h = make_hearings([{"case_id": "Z", "hearing_date": "01-01-2015"}, {"case_id": "A", "hearing_date": "02-01-2015"}])
    rep = validate_raw(raw(c, h))
    assert rep.ok
    assert rep.stats["hearings_orphaned"] == 1 and rep.stats["cases_blank_case_id"] == 1
    h2 = make_hearings([{"case_id": "Z", "hearing_date": "01-01-2015"}])
    with pytest.raises(IngestionError):
        assert_valid(raw(c, h2))
