import pandas as pd
import pytest

from tareekh_radar.classification import MLClassifier, RuleClassifier, classify_hearings
from tareekh_radar.cleaning import clean_dataset

from .conftest import make_cases, make_hearings, raw


@pytest.fixture
def rules(cfg):
    return RuleClassifier(cfg["classification"])


@pytest.mark.parametrize("text,expected", [
    ("Adjourned.", "ADJOURNMENT"),
    ("Presiding Officer on leave. Adjourned.", "ADJOURNMENT"),
    ("Time sought by defendant. Granted.", "ADJOURNMENT"),
    ("Summons issued to the defendant.", "PROCEDURAL_PROGRESS"),
    ("Written statement filed by defendant.", "PROCEDURAL_PROGRESS"),
    ("PW-1 examined and cross-examined.", "SUBSTANTIVE_PROGRESS"),
    ("Arguments heard. Put up for judgment.", "SUBSTANTIVE_PROGRESS"),
    ("Judgment pronounced. Suit decreed.", "SUBSTANTIVE_PROGRESS"),
    ("Evidence recorded. Adjourned for further evidence.", "SUBSTANTIVE_PROGRESS"),  # progress outranks next-date
])
def test_rule_categories(rules, text, expected):
    assert rules.classify_text(text).event_class == expected


def test_negation(rules):
    d = rules.classify_text("Evidence not recorded as witness absent. Adjourned.")
    assert d.event_class == "ADJOURNMENT"
    assert rules.classify_text("Notice not served. Fresh notice issued.").event_class == "PROCEDURAL_PROGRESS"


def test_missing_text_is_unknown_never_adjournment(rules):
    for t in (None, "", "   ", "NA", "-"):
        d = rules.classify_text(t)
        assert d.event_class == "UNKNOWN" and d.event_reason == "missing_description"


def test_ambiguous_and_low_confidence_stay_unknown(rules):
    assert rules.classify_text("Case called.").event_class == "UNKNOWN"
    d = rules.classify_text("Put up for evidence.")
    assert d.event_class == "UNKNOWN" and d.event_reason.startswith("below_rule_threshold")


def test_equal_priority_conflict_is_unknown(cfg):
    cfg["classification"]["rules"].append({"id": "clash", "category": "PROCEDURAL_PROGRESS", "priority": 50,
                                           "confidence": 0.9, "patterns": ["\\bpostponed\\b"]})
    d = RuleClassifier(cfg["classification"]).classify_text("Postponed.")
    assert d.event_class == "UNKNOWN" and d.event_reason.startswith("conflict")


def test_classify_hearings_human_override_and_ml(cfg):
    c = make_cases([{"case_id": "A", "court_id": "1", "case_type": "x"}])
    h = make_hearings([
        {"hearing_id": "1", "case_id": "A", "hearing_date": "01-01-2015", "last_order": "Adjourned"},
        {"hearing_id": "2", "case_id": "A", "hearing_date": "01-02-2015", "last_order": None},
        {"hearing_id": "3", "case_id": "A", "hearing_date": "01-03-2015", "last_order": "Some odd text"},
    ])
    cl = clean_dataset(raw(c, h), cfg)
    texts = pd.Series(["adjourned", "adjourned again", "evidence recorded", "pw1 examined", "summons issued",
                       "notice served", "adjourned to next date", "arguments heard"] * 3)
    labels = pd.Series(["ADJOURNMENT", "ADJOURNMENT", "SUBSTANTIVE_PROGRESS", "SUBSTANTIVE_PROGRESS",
                        "PROCEDURAL_PROGRESS", "PROCEDURAL_PROGRESS", "ADJOURNMENT", "SUBSTANTIVE_PROGRESS"] * 3)
    ml = MLClassifier(cfg["classification"]).fit(texts, labels)
    human = pd.DataFrame({"hearing_id": ["3"], "human_label": ["PROCEDURAL_PROGRESS"]})
    out = classify_hearings(cl.hearings, cfg, ml=ml, human_labels=human).set_index("hearing_id")
    assert out.loc["1", "event_class"] == "ADJOURNMENT" and out.loc["1", "event_method"] == "rules"
    assert out.loc["2", "event_class"] == "UNKNOWN"  # missing text never filled by ML
    assert out.loc["3", "event_class"] == "PROCEDURAL_PROGRESS" and out.loc["3", "event_method"] == "human"
    assert {"event_confidence", "event_reason", "event_rule_id"} <= set(out.columns)


def test_ml_abstains_below_threshold(cfg):
    cfg["classification"]["ml_min_probability"] = 0.99
    ml = MLClassifier(cfg["classification"]).fit(pd.Series(["adjourned", "evidence recorded"] * 5),
                                                pd.Series(["ADJOURNMENT", "SUBSTANTIVE_PROGRESS"] * 5))
    p = ml.predict(pd.Series(["completely unrelated words", ""]))
    assert list(p["ml_class"]) == ["UNKNOWN", "UNKNOWN"]
    assert p["ml_reason"].iloc[1] == "missing_description"
