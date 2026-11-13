import json

import pandas as pd
import pytest

from tareekh_radar.evaluation import (classification_metrics, compare_anomaly_methods, evaluate_classifiers,
                                      evaluate_review, export_review_sample, holdout_split, labels_from_review,
                                      sensitivity_analysis)
from tareekh_radar.pipeline import process
from tareekh_radar.privacy import build_id_map, pseudonym
from tareekh_radar.storage import list_datasets, write_tables

from .conftest import case_level_population, raw


@pytest.fixture
def processed(cfg):
    r = raw(case_level_population())
    r.manifest.name = "unit_case_level"
    res = process(r, cfg)
    write_tables(cfg, "unit_case_level", res.tables, res.meta)
    return res


def test_pipeline_pseudonymises_and_records_provenance(cfg, processed):
    a = processed.tables["anomalies"]
    assert a["case_id"].str.startswith("C-").all()
    assert not a["case_id"].isin(["OUTLIER"]).any()
    assert processed.meta["run_info"]["data_level"] == "case"
    assert processed.meta["run_info"]["config_hash"]
    assert "unit_case_level" in list_datasets(cfg)
    assert processed.meta["quality_report"]["classification"]["applicable"] is False


def test_pseudonym_deterministic_and_keyed():
    assert pseudonym("X", b"k1") == pseudonym("X", b"k1") != pseudonym("X", b"k2")
    m = build_id_map(pd.Series(["a", "b", "a"]), {"privacy": {}}, salt=b"s")
    assert len(m) == 2 and m["case_pid"].is_unique


def test_classification_metrics_and_holdout_no_leakage(cfg):
    m = classification_metrics(pd.Series(["ADJOURNMENT", "UNKNOWN", "SUBSTANTIVE_PROGRESS"]),
                               pd.Series(["ADJOURNMENT", "ADJOURNMENT", "UNKNOWN"]))
    assert m["true_unknown_predicted_adjournment"] == 1
    assert len(m["confusion_matrix"]) == 4 and m["macro_f1"] is not None
    df = pd.DataFrame({"text": [f"t{i % 10}" for i in range(100)], "label": "ADJOURNMENT", "case_id": range(100)})
    tr, te = holdout_split(df, "text", 0.3, 0)
    assert not set(tr["text"]) & set(te["text"])


def test_evaluate_classifiers_report(cfg):
    base = [("adjourned at request of counsel", "ADJOURNMENT"), ("summons issued to accused", "PROCEDURAL_PROGRESS"),
            ("pw1 examined", "SUBSTANTIVE_PROGRESS"), ("seen", "UNKNOWN")]
    rows = [{"text": f"{t} {i}", "label": l, "case_id": i} for i in range(15) for t, l in base]
    report, model = evaluate_classifiers(pd.DataFrame(rows), cfg)
    for k in ("rules", "ml", "hybrid"):
        assert "macro_f1" in report[k] and "confusion_matrix" in report[k]
    assert report["split"]["test_texts_seen_in_training_pct"] == 0.0
    assert model.fitted


def test_compare_methods_review_and_sensitivity(cfg, processed):
    a = processed.tables["anomalies"]
    comp = compare_anomaly_methods(a, cfg, mode="case")
    assert comp["n_scored"] > 0 and "statistical_peer_robust_z~isolation_forest" in comp["rank_correlation"]
    review = export_review_sample(a, processed.tables["hearings"], n=5)
    assert set(review["sample_group"]) == {"flagged_top", "unflagged_control"}
    assert "anomaly_score" not in review.columns  # blind review
    review["reviewer_verdict"] = ["pattern_confirmed" if g == "flagged_top" else "not_unusual" for g in review["sample_group"]]
    summ = evaluate_review(review)
    assert summ["by_sample_group"]["flagged_top"]["pattern_present_rate"] == 1.0
    comp2 = compare_anomaly_methods(a, cfg, labels_from_review(review), mode="case")
    assert comp2["labelled_evaluation"]["statistical_flag"]["false_positives"] == 0
    with pytest.raises(ValueError):
        evaluate_review(review.assign(reviewer_verdict="maybe"))
    cfg["evaluation"]["sensitivity"].update(drop_rates=[0.0, 0.2], mask_rates=[0.2], repeats=1)
    sens = sensitivity_analysis(processed.tables["cases"], None, cfg)
    assert set(sens["perturbation"]) == {"drop_records", "mask_listing_dates"}
    assert sens.loc[sens["rate"] == 0, "spearman_vs_baseline"].iloc[0] == 1.0


def test_api(cfg, processed):
    from fastapi.testclient import TestClient

    from tareekh_radar.api import create_app

    client = TestClient(create_app(cfg))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/datasets").json()[0]["name"] == "unit_case_level"
    ov = client.get("/datasets/unit_case_level/overview").json()
    assert ov["total_cases"] == len(processed.tables["anomalies"]) and ov["data_level"] == "case"
    an = client.get("/datasets/unit_case_level/anomalies", params={"limit": 5}).json()
    assert an["count"] >= 1
    cid = an["items"][0]["case_id"]
    case = client.get(f"/datasets/unit_case_level/cases/{cid}").json()
    assert case["explanation"]["contributions"]
    tl = client.get(f"/datasets/unit_case_level/cases/{cid}/timeline").json()
    assert {e["event"] for e in tl["events"]} >= {"Filed", "Last listed"}
    assert client.get("/datasets/nope/overview").status_code == 404
    assert client.get("/datasets/unit_case_level/cases/zzz").status_code == 404
    assert client.post("/classify", json={"text": ""}).json()["event_class"] == "UNKNOWN"
    assert client.post("/classify", json={"text": "Adjourned."}).json()["event_class"] == "ADJOURNMENT"


def _app_config(cfg, tmp_path, monkeypatch):
    import yaml

    path = tmp_path / "app_config.yaml"
    path.write_text(yaml.safe_dump({"paths": cfg["paths"], "dates": cfg["dates"]}), encoding="utf-8")
    monkeypatch.setenv("TAREEKH_CONFIG", str(path))


def test_streamlit_app_renders_every_module(cfg, processed, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    _app_config(cfg, tmp_path, monkeypatch)
    for page in ["Court Overview", "Case Timeline", "Anomaly Radar", "Data Quality Monitor", "Research Evaluation"]:
        at = AppTest.from_file("../app/streamlit_app.py", default_timeout=90)
        at.session_state["page"] = page
        if page == "Case Timeline":
            at.session_state["selected_case"] = processed.tables["anomalies"].query("flagged")["case_id"].iloc[0]
        at.run()
        assert not at.exception, f"{page}: {at.exception}"
        assert any("misconduct" in c.value for c in at.caption), page  # disclaimer on every module


def test_streamlit_app_without_data(cfg, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    _app_config(cfg, tmp_path, monkeypatch)
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=60)
    at.run()
    assert not at.exception
    assert any("No processed dataset" in w.value for w in at.warning)
