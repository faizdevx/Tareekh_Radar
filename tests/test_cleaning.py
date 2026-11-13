import pandas as pd

from tareekh_radar.cleaning import clean_dataset, normalize_case_type, normalize_stage, parse_dates

from .conftest import make_cases, make_hearings, raw

FMTS = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]


def test_parse_dates_formats_missing_invalid_out_of_range():
    s = pd.Series(["05-01-2015", "2015-01-06", "07/01/2015", None, "", "31-02-2019", "0001-11-11", "9201-08-19", "NA"])
    d, st = parse_dates(s, FMTS, "1950-01-01", "2030-01-01")
    assert d.iloc[0] == pd.Timestamp("2015-01-05")  # day-first
    assert d.iloc[1] == pd.Timestamp("2015-01-06")
    assert d.iloc[2] == pd.Timestamp("2015-01-07")
    assert list(st) == ["ok", "ok", "ok", "missing", "missing", "invalid", "out_of_range", "out_of_range", "missing"]
    assert d.iloc[3:].isna().all()


def test_case_type_normalisation_is_orthographic_only():
    assert normalize_case_type("O.S.") == normalize_case_type("os") == "OS"
    assert normalize_case_type("C.C.") == "CC"
    assert normalize_case_type("Sessions Case") == "SESSIONSCASE"  # not merged with "SC"
    assert normalize_case_type(None) == "UNKNOWN"
    assert normalize_case_type("Original Suit", {"CIVIL_SUIT": ["original suit", "os"]}) == "CIVIL_SUIT"


def test_stage_normalisation(cfg):
    p = cfg["stage_patterns"]
    assert normalize_stage("Appereance of accused", p) == "APPEARANCE"
    assert normalize_stage("appearence", p) == "APPEARANCE"
    assert normalize_stage("Prosecution Evidence", p) == "EVIDENCE"
    assert normalize_stage("Judgement", p) == "JUDGMENT"
    assert normalize_stage("blah", p) == "OTHER"
    assert normalize_stage(None, p) == "UNKNOWN"


def test_duplicates_removed_and_kept_in_log(cfg):
    c = make_cases([{"case_id": "A", "court_id": "1", "case_type": "x", "filing_date": "01-01-2014"},
                    {"case_id": "A", "court_id": "1", "case_type": "x"}])
    h = make_hearings([
        {"hearing_id": "h1", "case_id": "A", "hearing_date": "01-02-2015", "last_order": "Adjourned"},
        {"hearing_id": "h1", "case_id": "A", "hearing_date": "01-02-2015", "last_order": "Adjourned"},  # same id
        {"hearing_id": "h2", "case_id": "A", "hearing_date": "01-02-2015", "last_order": "ADJOURNED."},  # same content
        {"hearing_id": "h3", "case_id": "A", "hearing_date": "01-02-2015", "last_order": "Evidence recorded"},
    ])
    cl = clean_dataset(raw(c, h), cfg)
    assert len(cl.cases) == 1 and len(cl.hearings) == 2
    assert set(cl.duplicates["reason"]) == {"duplicate case_id", "duplicate hearing_id", "duplicate case/date/description"}
    assert cl.quality["duplicates"]["hearing_duplicate_rows"] == 2
    # repeated hearing date with different content is kept but flagged
    assert cl.hearings["data_quality_status"].str.contains("multiple_entries_same_date").all()


def test_chronology_and_missing_values_flagged_not_dropped(cfg):
    c = make_cases([{"case_id": "A", "court_id": "1", "case_type": "x", "filing_date": "01-01-2015",
                     "disposal_date": "01-01-2016"}])
    h = make_hearings([
        {"case_id": "A", "hearing_date": "01-06-2014", "last_order": "Notice issued"},  # before filing
        {"case_id": "A", "hearing_date": "01-06-2017", "last_order": None},  # after disposal, no text
        {"case_id": "A", "hearing_date": "garbage", "last_order": "Adjourned"},
        {"case_id": "A", "hearing_date": "01-03-2015", "last_order": "Adjourned"},  # out of source order
    ])
    cl = clean_dataset(raw(c, h), cfg)
    assert len(cl.hearings) == 4  # nothing silently discarded
    s = " ".join(cl.hearings["data_quality_status"])
    for flag in ("before_filing_date", "after_disposal_date", "missing_description", "invalid_date",
                 "source_order_not_chronological"):
        assert flag in s
    assert cl.hearings["event_text"].iloc[-1] in ("", "Adjourned")  # text preserved, not invented
    # chronological ordering: dated rows sorted, undated last
    dated = cl.hearings["hearing_date"].dropna()
    assert dated.is_monotonic_increasing and pd.isna(cl.hearings["hearing_date"].iloc[-1])


def test_case_level_cleaning_flags_and_status(cfg):
    c = make_cases([
        {"case_id": "P", "court_id": "1", "case_type": "cc", "filing_date": "2010-05-01", "last_listing_date": "2012-01-01"},
        {"case_id": "D", "court_id": "1", "case_type": "cc", "filing_date": "2010-05-01", "disposal_date": "2009-01-01"},
        {"case_id": "U", "court_id": "1", "case_type": "cc", "filing_date": "2010-05-01", "disposal_nature": "acquitted"},
        {"case_id": "F", "court_id": "1", "case_type": "cc", "filing_date": "2010-05-01", "first_listing_date": "2010-01-01",
         "last_listing_date": "9201-07-04"},
    ])
    cl = clean_dataset(raw(c), cfg)
    st = cl.cases.set_index("case_id")
    assert cl.level == "case"
    assert st.loc["P", "case_status"] == "PENDING"
    assert "disposal_before_filing" in st.loc["D", "data_quality_status"]
    assert st.loc["U", "case_status"] == "UNKNOWN"  # disposal nature but no date: not guessed
    assert "first_listing_before_filing" in st.loc["F", "data_quality_status"]
    assert st.loc["F", "last_listing_date_status"] == "out_of_range"
