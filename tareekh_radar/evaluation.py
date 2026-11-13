"""Research evaluation: classifier metrics, anomaly-method comparison, human review,
missing-data sensitivity, and group comparisons.

Leakage controls:
* Classifier hold-out splits are grouped (by case or by identical normalised text),
  and the report states how many test texts also appear in training.
* Anomaly comparisons never use ground-truth labels to fit anything.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr
from sklearn.metrics import (
    average_precision_score,
    cohen_kappa_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from .anomaly import run_anomaly_detection
from .classification import MLClassifier, RuleClassifier
from .cleaning import normalize_text
from .config import config_hash, resolve_path
from .features import compute_case_features
from .schemas import EVENT_CLASSES

REVIEW_VERDICTS = ("pattern_confirmed", "legitimate_explanation", "data_artifact", "not_unusual")


# ---------------------------------------------------------------- classification

def classification_metrics(y_true: pd.Series, y_pred: pd.Series, labels=EVENT_CLASSES) -> dict[str, Any]:
    y_true, y_pred = pd.Series(y_true).astype(str).reset_index(drop=True), pd.Series(y_pred).astype(str).reset_index(drop=True)
    labels = list(labels)
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    present = [i for i, lab in enumerate(labels) if s[i] > 0]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    abst = y_pred == "UNKNOWN"
    true_known = y_true != "UNKNOWN"
    return {
        "n": int(len(y_true)),
        "labels": labels,
        "per_class": {lab: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4),
                            "f1": round(float(f[i]), 4), "support": int(s[i])} for i, lab in enumerate(labels)},
        "macro_f1": round(float(np.mean([f[i] for i in present])), 4) if present else None,
        "accuracy": round(float((y_true == y_pred).mean()), 4) if len(y_true) else None,
        "confusion_matrix": cm.tolist(),
        "class_distribution_true": y_true.value_counts().to_dict(),
        "class_distribution_pred": y_pred.value_counts().to_dict(),
        "abstention_rate": round(float(abst.mean()), 4) if len(y_true) else None,
        "accuracy_on_non_abstained": round(float((y_true[~abst] == y_pred[~abst]).mean()), 4) if (~abst).any() else None,
        # Missing text must never be turned into an adjournment:
        "true_unknown_predicted_adjournment": int(((y_true == "UNKNOWN") & (y_pred == "ADJOURNMENT")).sum()),
        "known_events_coverage": round(float((~abst[true_known]).mean()), 4) if true_known.any() else None,
    }


def holdout_split(df: pd.DataFrame, group_by: str, test_size: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if group_by == "text":
        groups = df["text"].map(normalize_text)
    elif group_by in df.columns:
        groups = df[group_by]
    else:
        raise ValueError(f"Unknown group_by {group_by!r}")
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    tr, te = next(gss.split(df, groups=groups))
    return df.iloc[tr].copy(), df.iloc[te].copy()


def evaluate_classifiers(labelled: pd.DataFrame, cfg: dict, label_col: str = "label") -> tuple[dict, MLClassifier]:
    """Train ML on a grouped training split; compare rules, ML and hybrid on the held-out split.

    `labelled` needs columns: text, <label_col>, and case_id when grouping by case.
    """
    ccfg = cfg["classification"]
    df = labelled.dropna(subset=[label_col]).copy()
    df = df[df[label_col].isin(EVENT_CLASSES)]
    df["text"] = df["text"].fillna("")
    if len(df) < 20:
        raise ValueError(f"Need at least 20 labelled examples, got {len(df)}")
    train, test = holdout_split(df, ccfg["ml"]["group_by"], ccfg["ml"]["test_size"], ccfg["ml"]["random_state"])
    ml = MLClassifier(ccfg).fit(train["text"], train[label_col])
    rules = RuleClassifier(ccfg)
    rule_pred = test["text"].map(lambda t: rules.classify_text(t).event_class)
    ml_pred = ml.predict(test["text"])["ml_class"]
    hybrid = rule_pred.where(rule_pred != "UNKNOWN", ml_pred)
    hybrid[test["text"].map(normalize_text) == ""] = "UNKNOWN"
    train_texts = set(train["text"].map(normalize_text))
    overlap = float(test["text"].map(normalize_text).isin(train_texts).mean())
    report = {
        "split": {"group_by": ccfg["ml"]["group_by"], "train_n": len(train), "test_n": len(test),
                  "test_texts_seen_in_training_pct": round(100 * overlap, 2)},
        "rules": classification_metrics(test[label_col], rule_pred),
        "ml": classification_metrics(test[label_col], ml_pred),
        "hybrid": classification_metrics(test[label_col], hybrid),
    }
    if "case_id" in df.columns:
        report["split"]["case_overlap"] = int(len(set(train["case_id"]) & set(test["case_id"])))
    # retrain on all labelled data for deployment (evaluation numbers come from the hold-out only)
    final = MLClassifier(ccfg).fit(df["text"], df[label_col])
    final.trained_on["holdout_report_macro_f1"] = report["ml"]["macro_f1"]
    return report, final


def inter_annotator_agreement(ann: pd.DataFrame) -> dict[str, Any] | None:
    """Cohen's kappa for hearings labelled by exactly two annotators."""
    if "annotator" not in ann.columns:
        return None
    d = ann.dropna(subset=["human_label", "annotator"])
    multi = d.groupby("hearing_id").filter(lambda g: g["annotator"].nunique() >= 2)
    if multi.empty:
        return None
    pairs = multi.sort_values("annotator").groupby("hearing_id")["human_label"].apply(lambda s: s.iloc[:2].tolist())
    a, b = zip(*pairs)
    return {"n_double_annotated": len(pairs), "cohen_kappa": round(float(cohen_kappa_score(a, b)), 4),
            "raw_agreement": round(float(np.mean([x == y for x, y in zip(a, b)])), 4)}


# ---------------------------------------------------------------- annotation workflow

def export_annotation_sample(hearings: pd.DataFrame, n: int, seed: int = 0, show_suggestion: bool = False) -> pd.DataFrame:
    """Stratified sample (by rule class) for human labelling. Suggestions hidden by default to avoid anchoring."""
    rng = np.random.default_rng(seed)
    h = hearings.copy()
    strata = h["rule_class"] if "rule_class" in h else h["event_class"]
    parts = []
    per = max(1, n // max(1, strata.nunique()))
    for _, g in h.groupby(strata):
        parts.append(g.sample(min(per, len(g)), random_state=int(rng.integers(1 << 31))))
    sample = pd.concat(parts)
    if len(sample) < n:
        rest = h.drop(sample.index)
        sample = pd.concat([sample, rest.sample(min(n - len(sample), len(rest)), random_state=seed)])
    cols = ["hearing_id", "case_id", "hearing_date", "hearing_stage_raw", "last_action", "last_order", "next_hearing_purpose"]
    out = sample[[c for c in cols if c in sample.columns]].copy()
    if show_suggestion:
        out["suggested_label"] = sample["event_class"]
    out["human_label"] = ""
    out["annotator"] = ""
    out["notes"] = ""
    return out.sample(frac=1.0, random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------- anomaly comparison

def _topk_overlap(a: pd.Series, b: pd.Series, k: int) -> float | None:
    a, b = a.dropna(), b.dropna()
    if len(a) < k or len(b) < k:
        return None
    sa, sb = set(a.nlargest(k).index), set(b.nlargest(k).index)
    return round(len(sa & sb) / len(sa | sb), 4)


RAW_BASELINES = {
    "hearing": ["confirmed_adjournments", "adjournment_rate"],
    "case": ["case_age_days", "days_since_last_listing"],
}


def compare_anomaly_methods(anom: pd.DataFrame, cfg: dict, labels: pd.DataFrame | None = None,
                            mode: str | None = None) -> dict[str, Any]:
    """Compare statistical peer scoring, Isolation Forest and raw (un-normalised) rankings.

    labels: optional frame with case_id and boolean is_unusual_pattern, e.g. derived from a
    completed human review (see labels_from_review). No labels are invented.
    """
    mode = mode or ("hearing" if anom["total_hearings"].fillna(0).sum() > 0 else "case")
    df = anom.set_index("case_id")
    scored = df[(df["score_status"] == "scored")]
    methods = {"statistical_peer_robust_z": scored["anomaly_score"].astype(float),
               "isolation_forest": scored["if_score"].astype(float)}
    for col in RAW_BASELINES[mode]:
        methods[f"raw_{col}"] = scored[col].astype(float)
    out: dict[str, Any] = {"mode": mode, "n_scored": int(len(scored)),
                           "n_flagged_statistical": int(scored["flagged"].sum()),
                           "n_flagged_isolation_forest": int(scored["if_flag"].fillna(False).astype(bool).sum()),
                           "rank_correlation": {}, "topk_jaccard": {}}
    names = list(methods)
    for i, m1 in enumerate(names):
        for m2 in names[i + 1:]:
            both = methods[m1].notna() & methods[m2].notna()
            if both.sum() > 3:
                rho = spearmanr(methods[m1][both], methods[m2][both]).statistic
                out["rank_correlation"][f"{m1}~{m2}"] = None if pd.isna(rho) else round(float(rho), 4)
            for k in cfg["evaluation"]["top_k"]:
                out["topk_jaccard"][f"{m1}~{m2}@{k}"] = _topk_overlap(methods[m1], methods[m2], k)
    sf = scored["flagged"].astype(bool)
    iff = scored["if_flag"].fillna(False).astype(bool)
    out["flag_agreement"] = {"both": int((sf & iff).sum()), "statistical_only": int((sf & ~iff).sum()),
                             "isolation_forest_only": int((~sf & iff).sum())}
    # Does a raw ranking concentrate on a few courts? (peer-normalisation research question)
    k = max(cfg["evaluation"]["top_k"]) * 10
    for m in ("statistical_peer_robust_z", f"raw_{RAW_BASELINES[mode][0]}"):
        top = methods[m].dropna().nlargest(k).index
        share = scored.loc[top, "court_id"].value_counts(normalize=True)
        out.setdefault("top_ranked_court_concentration", {})[m] = {
            "top_n": int(len(top)), "distinct_courts": int(share.size),
            "largest_court_share": round(float(share.iloc[0]), 4) if len(share) else None}
    if labels is not None and len(labels):
        lab = labels.drop_duplicates("case_id", keep="last").set_index("case_id")["is_unusual_pattern"].astype(bool)
        common = scored.index.intersection(lab.index)
        y = lab.loc[common]
        res: dict[str, Any] = {"n_labelled": int(len(common)), "positives": int(y.sum()),
                               "note": "Labels come from human review of a sample; they cannot estimate recall over all cases."}
        if len(common) and 0 < y.sum() < len(y):
            for m, sc in methods.items():
                v = sc.loc[common]
                ok = v.notna()
                if ok.sum() > 1 and y[ok].nunique() == 2:
                    res[m] = {"roc_auc": round(float(roc_auc_score(y[ok], v[ok])), 4),
                              "average_precision": round(float(average_precision_score(y[ok], v[ok])), 4)}
        flagged = sf.loc[common]
        res["statistical_flag"] = {
            "true_positives": int((flagged & y).sum()), "false_positives": int((flagged & ~y).sum()),
            "false_negatives_among_labelled": int((~flagged & y).sum()),
            "false_positive_case_ids": list(common[(flagged & ~y).to_numpy()])[:50],
            "false_negative_case_ids": list(common[(~flagged & y).to_numpy()])[:50]}
        out["labelled_evaluation"] = res
    return out


def labels_from_review(review: pd.DataFrame) -> pd.DataFrame:
    d = review.copy()
    d["reviewer_verdict"] = d["reviewer_verdict"].fillna("").astype(str).str.strip().str.lower()
    d = d[d["reviewer_verdict"].isin(REVIEW_VERDICTS)]
    return pd.DataFrame({"case_id": d["case_id"],
                         "is_unusual_pattern": d["reviewer_verdict"].isin(["pattern_confirmed", "legitimate_explanation"])})


def group_comparison(anom: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dim in ("court_id", "case_type"):
        for val, g in anom.groupby(dim):
            sc = g["score_status"] == "scored"
            rows.append({"dimension": dim, "value": val, "cases": len(g), "scored": int(sc.sum()),
                         "flagged": int(g["flagged"].sum()),
                         "flag_rate_of_scored": round(float(g.loc[sc, "flagged"].mean()), 4) if sc.any() else None,
                         "median_anomaly_score": round(float(g.loc[sc, "anomaly_score"].median()), 3) if sc.any() else None,
                         "median_adjournment_rate": round(float(g["adjournment_rate"].median()), 4) if g["adjournment_rate"].notna().any() else None,
                         "mean_unknown_pct": round(float(g["unknown_record_percentage"].mean()), 2)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- sensitivity

def sensitivity_analysis(cases: pd.DataFrame, hearings: pd.DataFrame | None, cfg: dict) -> pd.DataFrame:
    """Re-run features + anomaly scoring under simulated data loss and compare with the baseline.

    hearing mode: drop hearing records / mask event descriptions to UNKNOWN.
    case mode:    drop case records / blank listing dates (first/last/next).
    """
    from .cleaning import empty_hearings
    from .schemas import CASE_LISTING_DATE_COLUMNS

    scfg = cfg["evaluation"]["sensitivity"]
    mode = "hearing" if hearings is not None and len(hearings) else "case"
    hearings = hearings if mode == "hearing" else empty_hearings()

    def run(c, h):
        return run_anomaly_detection(compute_case_features(c, h, cfg), cfg, mode).set_index("case_id")

    base = run(cases, hearings)
    base_score = base.loc[base["score_status"] == "scored", "anomaly_score"]
    base_flag = base["flagged"].astype(bool)
    k = min(cfg["evaluation"]["top_k"])
    rng = np.random.default_rng(scfg["random_state"])
    rows = []
    mask_kind = "mask_descriptions" if mode == "hearing" else "mask_listing_dates"
    for kind, rates in (("drop_records", scfg["drop_rates"]), (mask_kind, scfg["mask_rates"])):
        for rate in rates:
            for rep in range(int(scfg["repeats"]) if rate > 0 else 1):
                c, h = cases, hearings
                if rate > 0:
                    if mode == "hearing":
                        sel = rng.random(len(h)) < rate
                        if kind == "drop_records":
                            h = h[~sel]
                        else:
                            h = h.assign(event_class=np.where(sel, "UNKNOWN", h["event_class"]))
                    else:
                        sel = rng.random(len(c)) < rate
                        if kind == "drop_records":
                            c = c[~sel].reset_index(drop=True)
                        else:
                            c = c.copy()
                            for col in CASE_LISTING_DATE_COLUMNS:
                                if col in c:
                                    c.loc[sel, col] = pd.NaT
                a = run(c, h)
                s = a.loc[a["score_status"] == "scored", "anomaly_score"]
                common = base_score.index.intersection(s.index)
                rho = spearmanr(base_score[common], s[common]).statistic if len(common) > 3 else np.nan
                bf = base_flag.reindex(a.index).fillna(False).astype(bool)
                af = a["flagged"].astype(bool)
                rows.append({"perturbation": kind, "rate": rate, "repeat": rep, "cases": int(len(a)),
                             "scored_cases": int(len(s)), "flagged_cases": int(af.sum()),
                             "spearman_vs_baseline": round(float(rho), 4) if pd.notna(rho) else None,
                             f"top{k}_jaccard_vs_baseline": _topk_overlap(base_score, s, k),
                             "baseline_flags_retained": round(float(af[bf].mean()), 4) if bf.any() else None,
                             "new_flags_not_in_baseline": int((af & ~bf).sum())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- human review of top anomalies

def export_review_sample(anom: pd.DataFrame, hearings: pd.DataFrame, n: int, seed: int = 0,
                         include_controls: bool = True) -> pd.DataFrame:
    """Top-n flagged cases plus (optionally) n random scored-but-unflagged controls, shuffled.

    The sheet shows the case record but NOT the score, flag or explanation, so reviewers judge
    blind; the column `sample_group` must be hidden during review (or split off) and is used
    afterwards to compute precision on flagged cases and a false-negative estimate on controls.
    """
    top = anom[anom["flagged"]].sort_values("anomaly_score", ascending=False).head(n)
    parts = [top.assign(sample_group="flagged_top")]
    if include_controls:
        pool = anom[(anom["score_status"] == "scored") & ~anom["flagged"]]
        parts.append(pool.sample(min(n, len(pool)), random_state=seed).assign(sample_group="unflagged_control"))
    sel = pd.concat(parts).sample(frac=1.0, random_state=seed)
    has_h = hearings is not None and len(hearings) > 0
    rows = []
    for _, r in sel.iterrows():
        if has_h:
            hist = hearings[hearings["case_id"] == r["case_id"]].sort_values(["hearing_date", "source_row"])
            record = " || ".join(
                f"{'' if pd.isna(d) else pd.Timestamp(d).date()} [{c}] {t}" for d, c, t in
                zip(hist["hearing_date"], hist["event_class"], hist["event_text"].fillna("")))
        else:
            def dt(v):
                return "" if v is None or pd.isna(v) else str(pd.Timestamp(v).date())
            record = (f"filed {dt(r.get('filing_date'))}; first listed {dt(r.get('first_listing_date'))}; "
                      f"last listed {dt(r.get('last_listing_date'))}; next listing {dt(r.get('next_listing_date'))}; "
                      f"decided {dt(r.get('disposal_date'))}; status {r.get('case_status')}; "
                      f"purpose {r.get('current_purpose')}; disposal {r.get('disposal_nature')}; "
                      f"quality flags {r.get('case_quality_status')}")
        rows.append({"case_id": r["case_id"], "court_id": r["court_id"], "court_name": r.get("court_name"),
                     "case_type": r["case_type"], "case_status": r.get("case_status"), "record": record,
                     "source_reference": r.get("source_reference"), "sample_group": r["sample_group"],
                     "reviewer_verdict": "", "reviewer": "", "reviewer_notes": ""})
    return pd.DataFrame(rows)


def evaluate_review(review: pd.DataFrame) -> dict[str, Any]:
    d = review.copy()
    d["reviewer_verdict"] = d["reviewer_verdict"].fillna("").str.strip().str.lower()
    done = d[d["reviewer_verdict"] != ""]
    bad = set(done["reviewer_verdict"]) - set(REVIEW_VERDICTS)
    if bad:
        raise ValueError(f"Invalid reviewer_verdict values {sorted(bad)}; allowed {REVIEW_VERDICTS}")
    if done.empty:
        return {"reviewed": 0}
    counts = done["reviewer_verdict"].value_counts().to_dict()
    real = done["reviewer_verdict"].isin(["pattern_confirmed", "legitimate_explanation"])
    by_group = {}
    if "sample_group" in done.columns:
        for g, gd in done.groupby("sample_group"):
            gr = gd["reviewer_verdict"].isin(["pattern_confirmed", "legitimate_explanation"])
            by_group[g] = {"reviewed": int(len(gd)), "pattern_present_rate": round(float(gr.mean()), 4),
                           "data_artifact_rate": round(float((gd["reviewer_verdict"] == "data_artifact").mean()), 4)}
    return {"reviewed": int(len(done)), "verdict_counts": counts, "by_sample_group": by_group,
            "pattern_present_rate": round(float(real.mean()), 4),
            "data_artifact_rate": round(float((done["reviewer_verdict"] == "data_artifact").mean()), 4),
            "false_positive_rate": round(float((done["reviewer_verdict"] == "not_unusual").mean()), 4),
            "note": ("flagged_top pattern_present_rate estimates precision of flags; unflagged_control "
                     "pattern_present_rate estimates the miss rate among unflagged scored cases.")}


# ---------------------------------------------------------------- experiment tracking

def new_run_dir(cfg: dict, label: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = resolve_path(cfg, "runs_dir") / f"{ts}_{config_hash(cfg)}_{label}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return d


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
