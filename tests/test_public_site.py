import json

import numpy as np
import pandas as pd

from tareekh_radar.categories import assign_categories, category_from_act, category_from_type
from tareekh_radar.public.build import build_site_data
from tareekh_radar.public.stats import group_stats, kaplan_meier, km_curve, km_quantile, outcome_group


def test_kaplan_meier_with_censoring():
    t, s = kaplan_meier(np.array([1, 2, 2, 3, 4]), np.array([1, 0, 1, 1, 0]))
    assert list(t) == [1, 2, 3, 4]
    assert np.allclose(s, [0.8, 0.6, 0.3, 0.3])
    assert km_quantile(t, s, 0.5) == 3
    assert km_quantile(t, s, 0.9) is None  # never reached: only 70% decided within follow-up
    assert km_curve(t, s, 0) == [0.0]


def test_pending_cases_are_censored_not_dropped():
    # all decided at 100 days vs. half still pending at 1000 days: median must not look like 100
    snap = pd.Timestamp("2020-01-01")
    f = pd.Timestamp("2010-01-01")
    rows = [{"filing_date": f, "disposal_date": f + pd.Timedelta(days=100), "case_status": "DISPOSED", "outcome_group": "dismissed"}] * 40
    rows += [{"filing_date": f, "disposal_date": pd.NaT, "case_status": "PENDING", "outcome_group": None}] * 60
    df = pd.DataFrame(rows)
    for c in ("first_listing_date", "next_listing_date"):
        df[c] = pd.NaT
    # pending cases are censored at their own last recorded listing (here 1000 days after filing)
    df["last_listing_date"] = [pd.NaT] * 40 + [f + pd.Timedelta(days=1000)] * 60
    s = group_stats(df, snap, 30, 12)
    assert s["time_to_decision_days"]["p50"] is None  # only 40% decided within follow-up
    assert s["time_to_decision_days"]["max_followup"] == 1000  # not the later snapshot
    assert s["n_pending"] == 60 and s["outcomes"] == {"dismissed": 1.0}
    # without a last listing date, a pending case cannot be placed in time and is excluded
    df2 = df.assign(last_listing_date=pd.NaT)
    s2 = group_stats(df2, snap, 30, 12)
    assert s2["n_excluded_bad_dates"] == 60 and s2["time_to_decision_days"]["p50"] == 100


def test_small_groups_suppressed():
    df = pd.DataFrame({"filing_date": [pd.Timestamp("2010-01-01")] * 5, "case_status": "PENDING", "outcome_group": None})
    assert group_stats(df, pd.Timestamp("2020-01-01"), 30, 12)["suppressed"] is True


def test_outcome_groups():
    assert outcome_group("Acquitted") == "acquitted"
    assert outcome_group("disposal in lok adalat") == "lok_adalat"
    assert outcome_group("transferred") == "moved"
    assert outcome_group("judgement") == "unspecified"
    assert outcome_group(None) is None


def test_case_categories():
    assert category_from_type("M.A.C.P.") == "motor_accident"
    assert category_from_type("Cri. Bail Appln.") == "bail"
    assert category_from_type("O.S.") == "civil_suit"
    assert category_from_type("Cri. Case") == "criminal_case"
    assert category_from_type("H.M.A.") == "matrimonial"
    assert category_from_type("RCT") == "other"  # unclear abbreviation stays unclear
    assert category_from_act("Negotiable Instruments Act", "138") == "cheque_bounce"
    assert category_from_act("Code of Criminal Procedure", "125") == "maintenance"
    assert category_from_act("Code of Criminal Procedure", "200") is None
    s = assign_categories(pd.Series(["S.C.C.", "S.C.C."]), pd.Series(["Negotiable Instruments Act", ""]), pd.Series(["138", ""]))
    assert list(s) == ["cheque_bounce", "criminal_case"]


def test_build_site_data_end_to_end(cfg, tmp_path):
    rng = np.random.default_rng(1)
    rows = []
    for i in range(120):
        filing = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
        decided = i % 3 != 0
        dec = filing + pd.Timedelta(days=int(rng.integers(100, 1500)))
        rows.append({"case_id": f"X{i}", "court_id": "26-01-01", "case_type": "M.A.C.P.", "filing_date": filing.strftime("%Y-%m-%d"),
                     "disposal_date": dec.strftime("%Y-%m-%d") if decided else None, "case_status": None,
                     "first_listing_date": (filing + pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
                     "last_listing_date": (dec if decided else pd.Timestamp("2019-06-01")).strftime("%Y-%m-%d"),
                     "next_listing_date": None if decided else "2019-08-01", "disposal_nature": "award" if decided else None,
                     "case_category": "motor_accident", "state_code": "26", "state_name": "Delhi", "district_id": "26-01",
                     "district_name": "Central", "filing_year": "2010", "current_purpose": "evidence", "source_reference": "unit"})
    p = tmp_path / "cases.parquet"
    pd.DataFrame(rows).to_parquet(p, index=False)
    out = tmp_path / "site"
    meta = build_site_data([p], out, cfg, min_n=30)
    assert meta["totals"]["cases"] == 120 and meta["states"][0]["districts"][0]["id"] == "26-01"
    d = json.loads((out / "districts" / "26-01.json").read_text(encoding="utf-8"))
    mc = d["categories"]["motor_accident"]
    assert mc["outcomes"] == {"allowed": 1.0}
    assert mc["next_hearing_gap_days"]["p50"] == 61
    assert 0 < mc["time_to_decision_days"]["p50"] < 1500
    text = (out / "districts" / "26-01.json").read_text(encoding="utf-8")
    assert "X1" not in text  # no individual case ids in published data
    assert json.loads((out / "national.json").read_text(encoding="utf-8"))["categories"]["motor_accident"]["n"] == 120
