"""Hearing event classification: transparent rules + TF-IDF/LogReg baseline.

Categories: ADJOURNMENT, PROCEDURAL_PROGRESS, SUBSTANTIVE_PROGRESS, UNKNOWN.

Guarantees:
* Missing/empty descriptions are UNKNOWN (reason "missing_description") - never adjournment.
* Conflicting equal-priority rules yield UNKNOWN (reason "conflict").
* Low-confidence decisions yield UNKNOWN.
* Human labels, when supplied, override automatic decisions (method "human").
* Every decision records method, rule id, confidence and reason.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .cleaning import normalize_text
from .schemas import CLASSIFICATION_COLUMNS, EVENT_CLASSES

UNKNOWN = "UNKNOWN"


@dataclass
class Decision:
    event_class: str
    event_confidence: float
    event_method: str
    event_rule_id: str | None
    event_subtype: str | None
    event_reason: str

    def as_tuple(self) -> tuple:
        return (self.event_class, self.event_confidence, self.event_method,
                self.event_rule_id, self.event_subtype, self.event_reason)


class RuleClassifier:
    """Configurable regex rule classifier with priorities, negation and confidence."""

    def __init__(self, cls_cfg: dict):
        self.min_conf = float(cls_cfg.get("rule_min_confidence", 0.6))
        self.neg = re.compile(cls_cfg.get("negation_pattern", r"\b(not|no)\b"))
        self.neg_window = int(cls_cfg.get("negation_window_chars", 20))
        self.rules = []
        for r in cls_cfg["rules"]:
            self.rules.append({
                **r,
                "compiled": [re.compile(p) for p in r["patterns"]],
            })

    def _negated(self, text: str, m: re.Match) -> bool:
        span = text[max(0, m.start() - self.neg_window): m.end()]
        return bool(self.neg.search(span))

    def matches(self, text: str) -> list[dict]:
        hits = []
        for r in self.rules:
            found = None
            for pat in r["compiled"]:
                for m in pat.finditer(text):
                    if r.get("negatable") and self._negated(text, m):
                        continue
                    found = m
                    break
                if found is not None:
                    break
            if found is not None:
                hits.append({"id": r["id"], "category": r["category"], "priority": r["priority"],
                             "confidence": float(r["confidence"]), "subtype": r.get("subtype"),
                             "match": found.group(0)})
        return hits

    def classify_text(self, text: str) -> Decision:
        norm = normalize_text(text)
        if not norm:
            return Decision(UNKNOWN, 0.0, "rules", None, None, "missing_description")
        hits = self.matches(norm)
        if not hits:
            return Decision(UNKNOWN, 0.0, "rules", None, None, "no_rule_matched")
        top_priority = max(h["priority"] for h in hits)
        top = [h for h in hits if h["priority"] == top_priority]
        cats = {h["category"] for h in top}
        if len(cats) > 1:
            ids = ",".join(sorted(h["id"] for h in top))
            return Decision(UNKNOWN, 0.0, "rules", ids, None, f"conflict:{ids}")
        cat = cats.pop()
        # Combine independent same-category evidence: 1 - prod(1 - c)
        conf = 1.0 - float(np.prod([1.0 - h["confidence"] for h in top]))
        conf = round(min(conf, 0.99), 3)
        best = max(top, key=lambda h: h["confidence"])
        if conf < self.min_conf:
            return Decision(UNKNOWN, conf, "rules", best["id"], best.get("subtype"),
                            f"below_rule_threshold:{best['id']}")
        lower = [h for h in hits if h["priority"] < top_priority]
        reason = f"matched:{best['match']!r}"
        if lower:
            reason += " (outranked:" + ",".join(sorted({h['id'] for h in lower})) + ")"
        return Decision(cat, conf, "rules", best["id"], best.get("subtype"), reason)


class MLClassifier:
    """TF-IDF + Logistic Regression baseline. Abstains (UNKNOWN) below a probability threshold."""

    def __init__(self, cls_cfg: dict):
        mcfg = cls_cfg["ml"]
        self.min_prob = float(cls_cfg.get("ml_min_probability", 0.65))
        self.params = mcfg
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=tuple(mcfg["ngram_range"]), min_df=mcfg["min_df"],
                                      max_features=mcfg["max_features"], sublinear_tf=True)),
            ("clf", LogisticRegression(C=mcfg["C"], class_weight=mcfg["class_weight"],
                                       max_iter=mcfg["max_iter"], random_state=mcfg["random_state"])),
        ])
        self.fitted = False
        self.trained_on: dict[str, Any] = {}

    def fit(self, texts: pd.Series, labels: pd.Series) -> "MLClassifier":
        X = texts.map(normalize_text)
        keep = (X != "") & labels.isin(EVENT_CLASSES)
        X, y = X[keep], labels[keep]
        if y.nunique() < 2:
            raise ValueError("Need at least two classes with non-empty text to train the ML classifier")
        self.pipeline.fit(X, y)
        self.fitted = True
        self.trained_on = {"n": int(len(y)), "class_counts": y.value_counts().to_dict()}
        return self

    def predict(self, texts: pd.Series) -> pd.DataFrame:
        if not self.fitted:
            raise RuntimeError("ML classifier is not trained")
        X = texts.map(normalize_text)
        out = pd.DataFrame(index=texts.index)
        out["ml_class"] = UNKNOWN
        out["ml_probability"] = 0.0
        out["ml_reason"] = "missing_description"
        has = X != ""
        if has.any():
            proba = self.pipeline.predict_proba(X[has])
            classes = self.pipeline.classes_
            best = proba.argmax(axis=1)
            pmax = proba.max(axis=1)
            pred = classes[best]
            out.loc[has, "ml_probability"] = np.round(pmax, 3)
            confident = pmax >= self.min_prob
            out.loc[has, "ml_class"] = np.where(confident, pred, UNKNOWN)
            out.loc[has, "ml_reason"] = np.where(confident, "ml_confident", [f"ml_abstain:{p}" for p in pred])
        return out

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self.pipeline, "min_prob": self.min_prob, "params": self.params,
                     "trained_on": self.trained_on}, path)

    @classmethod
    def load(cls, path: str | Path, cls_cfg: dict) -> "MLClassifier":
        blob = joblib.load(path)
        obj = cls(cls_cfg)
        obj.pipeline = blob["pipeline"]
        obj.trained_on = blob.get("trained_on", {})
        obj.fitted = True
        return obj


def classify_hearings(
    hearings: pd.DataFrame,
    cfg: dict,
    ml: MLClassifier | None = None,
    human_labels: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach classification columns to a cleaned hearings frame."""
    cls_cfg = cfg["classification"]
    mode = cls_cfg.get("mode", "hybrid")
    rules = RuleClassifier(cls_cfg)
    out = hearings.copy()
    decisions = [rules.classify_text(t) for t in out["event_text"]]
    out[CLASSIFICATION_COLUMNS] = pd.DataFrame([d.as_tuple() for d in decisions], index=out.index)
    out["rule_class"] = out["event_class"]

    if ml is not None and mode in {"ml", "hybrid"}:
        pred = ml.predict(out["event_text"])
        out["ml_class"], out["ml_probability"] = pred["ml_class"], pred["ml_probability"]
        if mode == "ml":
            use = pd.Series(True, index=out.index)
        else:
            use = (out["rule_class"] == UNKNOWN) & (pred["ml_class"] != UNKNOWN)
        use &= ~out["text_missing"] if "text_missing" in out else True
        out.loc[use, "event_class"] = pred.loc[use, "ml_class"]
        out.loc[use, "event_confidence"] = pred.loc[use, "ml_probability"]
        out.loc[use, "event_method"] = "ml"
        out.loc[use, "event_subtype"] = None
        out.loc[use, "event_reason"] = pred.loc[use, "ml_reason"]
        if mode == "ml":
            abstain = ~use | (pred["ml_class"] == UNKNOWN)
            out.loc[abstain, "event_class"] = UNKNOWN
            out.loc[abstain, "event_method"] = "ml"
            out.loc[abstain, "event_reason"] = pred.loc[abstain, "ml_reason"]
    else:
        out["ml_class"] = None
        out["ml_probability"] = np.nan

    if human_labels is not None and len(human_labels):
        hl = human_labels.dropna(subset=["human_label"]).drop_duplicates("hearing_id", keep="last")
        hl = hl[hl["human_label"].isin(EVENT_CLASSES)].set_index("hearing_id")["human_label"]
        hit = out["hearing_id"].isin(hl.index)
        out.loc[hit, "event_class"] = out.loc[hit, "hearing_id"].map(hl)
        out.loc[hit, "event_confidence"] = 1.0
        out.loc[hit, "event_method"] = "human"
        out.loc[hit, "event_reason"] = "human_annotation"

    # Safety net: missing text is never anything but UNKNOWN unless a human said otherwise.
    if "text_missing" in out:
        guard = out["text_missing"] & (out["event_method"] != "human")
        out.loc[guard, "event_class"] = UNKNOWN
    out["event_confidence"] = out["event_confidence"].astype(float)
    return out


def decision_log(classified: pd.DataFrame) -> pd.DataFrame:
    """Per-hearing classification audit trail."""
    cols = ["hearing_id", "case_id", "event_text", "rule_class", "ml_class", "ml_probability", *CLASSIFICATION_COLUMNS]
    return classified[[c for c in cols if c in classified.columns]].copy()


def load_human_labels(path: str | Path) -> pd.DataFrame:
    """Read a completed annotation file; validates label values."""
    from .ingestion import read_table

    df = read_table(path)
    if "hearing_id" not in df.columns or "human_label" not in df.columns:
        raise ValueError("Annotation file must have hearing_id and human_label columns")
    df["human_label"] = df["human_label"].map(lambda v: None if v is None else str(v).strip().upper() or None)
    bad = df["human_label"].notna() & ~df["human_label"].isin(EVENT_CLASSES)
    if bad.any():
        raise ValueError(f"Invalid human_label values: {sorted(df.loc[bad, 'human_label'].unique())}; "
                         f"allowed: {EVENT_CLASSES}")
    return df


def save_rule_report(path: str | Path, classified: pd.DataFrame) -> None:
    rep = {
        "class_distribution": classified["event_class"].value_counts().to_dict(),
        "method_distribution": classified["event_method"].value_counts().to_dict(),
        "rule_hits": classified["event_rule_id"].fillna("none").value_counts().to_dict(),
        "unknown_reasons": classified.loc[classified["event_class"] == UNKNOWN, "event_reason"]
        .str.split(":").str[0].value_counts().to_dict(),
    }
    Path(path).write_text(json.dumps(rep, indent=2), encoding="utf-8")
