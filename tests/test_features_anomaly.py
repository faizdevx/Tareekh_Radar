import json

import numpy as np
import pandas as pd

from tareekh_radar.anomaly import run_anomaly_detection
from tareekh_radar.classification import classify_hearings
from tareekh_radar.cleaning import clean_dataset
from tareekh_radar.features import compute_case_features, longest_streak, stage_returns, trailing_streak

from .conftest import case_level_population, hearing_series, make_cases, make_hearings, raw

ADJ, PROC, SUB, UNK = "ADJOURNMENT", "PROCEDURAL_PROGRESS", "SUBSTANTIVE_PROGRESS", "UNKNOWN"


def _hearing_features(cfg, cases_rows, hearing_rows):
    cl = clean_dataset(raw(make_cases(cases_rows), make_hearings(hearing_rows)), cfg)
    h = classify_hearings(cl.hearings, cfg)
    return compute_case_features(cl.cases, h, cfg).set_index("case_id")


def test_streak_helpers():
    assert longest_streak([ADJ, ADJ, UNK, ADJ, PROC]) == (2, 0, 1)  # unknown breaks (conservative)
    assert longest_streak([ADJ, ADJ, UNK, ADJ, PROC], unknown_breaks=False)[0] == 3  # upper bound
    assert trailing_streak([PROC, ADJ, ADJ]) == 2
    n, longest, idx = stage_returns(["A", "A", "B", "A", "UNKNOWN", "B", "C"])
    assert n == 2 and longest == 2 and idx == [3, 5]


def test_edge_cases(cfg):
    c = [{"case_id": k, "court_id": "1", "case_type": "x", "filing_date": "01-01-2014"} for k in "ABCDE"]
    h = (hearing_series("A", "2015-01-01", ["Adjourned"])  # single hearing
         + hearing_series("B", "2015-01-01", [None, "", None, "Case called."])  # all unknown
         + hearing_series("C", "2015-01-01", ["Summons issued.", "PW-1 examined.", "Arguments heard."])  # no adjournments
         + [{"hearing_id": "D1", "case_id": "D", "hearing_date": None, "last_order": "Adjourned"},
            {"hearing_id": "D2", "case_id": "D", "hearing_date": "bad", "last_order": "Adjourned"}])  # missing dates
    f = _hearing_features(cfg, c, h)
    assert f.loc["A", "total_hearings"] == 1 and np.isnan(f.loc["A", "adjournment_rate"])
    assert "adjournment_rate" in json.loads(f.loc["A", "unavailable_metrics"])
    assert f.loc["B", "unknown_events"] == 4 and f.loc["B", "confirmed_adjournments"] == 0
    assert not f.loc["B", "eligible"]
    assert f.loc["C", "confirmed_adjournments"] == 0 and f.loc["C", "adjournment_rate"] == 0
    assert f.loc["D", "dated_hearings"] == 0 and np.isnan(f.loc["D", "max_hearing_gap"])
    assert f.loc["E", "ineligible_reason"] == "no_hearings_recorded"


def test_feature_values(cfg):
    texts = ["Summons issued.", "Adjourned.", "Adjourned.", None, "Adjourned.", "PW-1 examined.", "Adjourned."]
    stages = ["Summons", "Evidence", "Evidence", "Evidence", "Summons", "Evidence", "Evidence"]
    f = _hearing_features(cfg, [{"case_id": "A", "court_id": "1", "case_type": "x", "filing_date": "01-01-2014"}],
                          hearing_series("A", "2015-01-01", texts, stages, step_days=10)).loc["A"]
    assert f["total_hearings"] == 7 and f["confirmed_adjournments"] == 4 and f["unknown_events"] == 1
    assert f["adjournment_rate"] == round(4 / 7, 4)
    assert f["max_non_progress_streak"] == 2 and f["max_non_progress_streak_upper"] == 3
    assert f["non_progress_streak"] == 1
    assert f["repeated_stage_count"] == 2  # Evidence -> Summons -> Evidence
    assert f["median_hearing_interval"] == 10 and f["maximum_hearing_gap"] == 10
    assert f["days_since_last_substantive_basis"] == "since_last_substantive_event"


def test_repeated_hearing_dates_counted(cfg):
    h = [{"hearing_id": f"A{i}", "case_id": "A", "hearing_date": d, "last_order": t} for i, (d, t) in enumerate(
        [("01-01-2015", "Adjourned"), ("01-01-2015", "Notice issued"), ("01-03-2015", "Adjourned")])]
    f = _hearing_features(cfg, [{"case_id": "A", "court_id": "1", "case_type": "x"}], h).loc["A"]
    assert f["same_day_entries"] == 1 and f["maximum_hearing_gap"] == 59


def test_case_level_features_and_scoring(cfg):
    cl = clean_dataset(raw(case_level_population()), cfg)
    f = compute_case_features(cl.cases, cl.hearings, cfg)
    assert f.attrs["data_level"] == "case"
    fi = f.set_index("case_id")
    assert np.isnan(fi.loc["OUTLIER", "adjournment_rate"])  # hearing metrics unavailable, not zero
    assert fi.loc["OUTLIER", "days_since_last_listing"] > 2000
    disposed = fi[fi["case_status"] == "DISPOSED"]
    assert disposed["days_since_last_listing"].isna().all()
    a = run_anomaly_detection(f, cfg).set_index("case_id")
    o = a.loc["OUTLIER"]
    assert o["flagged"] and "days_since_last_listing" in json.loads(o["contributing_features"])
    e = json.loads(o["anomaly_explanation_json"])
    c = e["contributions"][0]
    assert c["supporting_fields"]["last_listing_date"] == "2014-05-01"
    assert e["peer_group"]["size"] >= cfg["anomaly"]["min_peer_size"]
    assert "PENDING" in e["peer_group"]["key"]  # pending never compared with disposed
    assert "misconduct" in e["disclaimer"]
    assert a["flagged"].mean() < 0.1


def test_no_comparable_peer_group(cfg):
    pop = case_level_population(n_per_group=40, outlier=False)
    lonely = pop.iloc[[0]].copy()
    lonely["case_id"], lonely["case_type"] = "LONELY", "RARE_TYPE"
    lonely["case_category"] = "RARE"
    cl = clean_dataset(raw(pd.concat([pop, lonely], ignore_index=True)), cfg)
    a = run_anomaly_detection(compute_case_features(cl.cases, cl.hearings, cfg), cfg).set_index("case_id")
    assert a.loc["LONELY", "score_status"] == "no_comparable_peer_group"
    assert not a.loc["LONELY", "flagged"] and np.isnan(a.loc["LONELY", "anomaly_score"])


def test_hearing_mode_peer_comparison_flags_excess_adjournments(cfg):
    cases, hearings = [], []
    for i in range(40):
        cid = f"N{i}"
        cases.append({"case_id": cid, "court_id": "1", "case_type": "x", "filing_date": "01-01-2014"})
        seq = ["Summons issued.", "Adjourned.", "PW-1 examined.", "Adjourned.", "Arguments heard.", "Adjourned."]
        hearings += hearing_series(cid, "2015-01-01", seq[: 4 + i % 3], step_days=30 + i % 5)
    cases.append({"case_id": "X", "court_id": "1", "case_type": "x", "filing_date": "01-01-2014"})
    hearings += hearing_series("X", "2015-01-01", ["Summons issued."] + ["Adjourned."] * 14, step_days=30)
    f = _hearing_features(cfg, cases, hearings).reset_index()
    a = run_anomaly_detection(f, cfg).set_index("case_id")
    assert a.loc["X", "flagged"]
    contrib = json.loads(a.loc["X", "contributing_features"])
    assert "max_non_progress_streak" in contrib
    e = json.loads(a.loc["X", "anomaly_explanation_json"])
    ids = next(c for c in e["contributions"] if c["feature"] == "max_non_progress_streak")["supporting_hearing_ids"]
    assert len(ids) == 14 and all(i.startswith("X-") for i in ids)
    assert a.loc["X", "anomaly_percentile"] > 0.95
    assert not a.drop(index="X")["flagged"].any()
