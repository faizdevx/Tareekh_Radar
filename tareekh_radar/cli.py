"""Command-line interface.

    python -m tareekh_radar.cli ddl-extract --dta data/raw/ddl/cases_clean_2010.dta --states 26 --out data/raw/ddl/delhi_2010
    python -m tareekh_radar.cli process --cases data/raw/ddl/delhi_2010/cases.parquet --mapping data/raw/ddl/delhi_2010/mapping.yaml
    python -m tareekh_radar.cli evaluate --dataset ddl_2010_26 [--review-file F]
    python -m tareekh_radar.cli review-export --dataset ddl_2010_26
    python -m tareekh_radar.cli review-evaluate --file F
    # hearing-level sources only (e.g. DAKSH hearing data):
    python -m tareekh_radar.cli process --cases C --hearings H --mapping M
    python -m tareekh_radar.cli annotate-export --dataset N --n 300
    python -m tareekh_radar.cli train-classifier --labels completed_annotations.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from .config import load_config, resolve_path
from .ingestion import IngestionError, read_table


def _cfg(args) -> dict:
    return load_config(args.config)


def cmd_ddl_extract(args) -> int:
    from .adapters.ddl import extract

    states = [s.zfill(2) for s in args.states.split(",")] if args.states else None
    districts = args.districts.split(",") if args.districts else None
    keys_dir = Path(args.keys_dir) if args.keys_dir else Path(args.dta).parent
    paths = extract(args.dta, keys_dir, args.out, states=states, districts=districts, name=args.name)
    print(f"Extracted real DDL case records: {paths['cases']}\nMapping/provenance: {paths['mapping']}")
    return 0


def cmd_process(args) -> int:
    from .pipeline import run_pipeline, summarize

    cfg = _cfg(args)
    if args.rules_only:
        cfg["classification"]["mode"] = "rules"
    if args.reference_date:
        cfg["features"]["case_reference_date"] = args.reference_date
    out, result = run_pipeline(args.cases, args.hearings, cfg, mapping_path=args.mapping, dataset_name=args.name,
                               model_path=args.model, human_labels_path=args.human_labels)
    print(json.dumps(summarize(result), indent=2, default=str))
    print(f"Outputs: {out}")
    return 0


def cmd_train_classifier(args) -> int:
    from .evaluation import evaluate_classifiers, inter_annotator_agreement, new_run_dir, save_json
    from .pipeline import default_model_path

    cfg = _cfg(args)
    labels = read_table(args.labels)
    if args.label_col not in labels.columns:
        raise IngestionError(f"Label column {args.label_col!r} not in {args.labels}")
    if args.text_col in labels.columns:
        labels["text"] = labels[args.text_col]
    else:
        parts = [c for c in cfg["classification"]["text_fields"] if c in labels.columns]
        if not parts:
            raise IngestionError(f"Label file needs {args.text_col!r} or {cfg['classification']['text_fields']}")
        labels["text"] = labels[parts].apply(lambda r: " | ".join(v for v in r if isinstance(v, str) and v.strip()), axis=1)
    labels["label"] = labels[args.label_col].astype(str).str.strip().str.upper()
    report, model = evaluate_classifiers(labels, cfg, label_col="label")
    iaa = inter_annotator_agreement(labels.rename(columns={"label": "human_label"}))
    if iaa:
        report["inter_annotator_agreement"] = iaa
    report["label_source"] = {"file": str(args.labels), "label_column": args.label_col}
    model_path = Path(args.model) if args.model else default_model_path(cfg)
    model.save(model_path)
    run = new_run_dir(cfg, "classifier")
    save_json(run / "classifier_report.json", report)
    print(json.dumps({k: report[k]["macro_f1"] for k in ("rules", "ml", "hybrid")}, indent=2))
    print(f"Model: {model_path}\nReport: {run}")
    return 0


def cmd_evaluate(args) -> int:
    from .evaluation import (compare_anomaly_methods, evaluate_review, group_comparison, labels_from_review,
                             new_run_dir, save_json, sensitivity_analysis)
    from .storage import dataset_dir, load_json, load_table

    cfg = _cfg(args)
    cases = load_table(cfg, args.dataset, "cases")
    hearings = load_table(cfg, args.dataset, "hearings")
    anom = load_table(cfg, args.dataset, "anomalies")
    run_info = load_json(cfg, args.dataset, "run_info")
    mode = run_info.get("data_level", "hearing")
    labels, review_summary = None, None
    if args.review_file:
        review = read_table(args.review_file)
        review_summary = evaluate_review(review)
        labels = labels_from_review(review)
    run = new_run_dir(cfg, f"eval_{args.dataset}")
    comparison = compare_anomaly_methods(anom, cfg, labels, mode)
    save_json(run / "anomaly_comparison.json", comparison)
    groups = group_comparison(anom)
    groups.to_csv(run / "group_comparison.csv", index=False)
    report = {"dataset": args.dataset, "data_level": mode, "manifest": load_json(cfg, args.dataset, "manifest"),
              "anomaly_comparison": comparison, "human_review": review_summary,
              "classification": ("not applicable: source has no per-hearing records" if mode == "case" else
                                 "see train-classifier reports (requires human-labelled hearings)")}
    if not args.skip_sensitivity:
        for c in ("filing_date", "disposal_date", "first_listing_date", "last_listing_date", "next_listing_date"):
            if c in cases:
                cases[c] = pd.to_datetime(cases[c])
        if len(hearings):
            hearings["hearing_date"] = pd.to_datetime(hearings["hearing_date"])
        sens = sensitivity_analysis(cases, hearings if len(hearings) else None, cfg)
        sens.to_csv(run / "sensitivity.csv", index=False)
        sens.to_csv(dataset_dir(cfg, args.dataset) / "sensitivity.csv", index=False)
        report["sensitivity_summary"] = (sens.groupby(["perturbation", "rate"]).mean(numeric_only=True)
                                         .reset_index().to_dict("records"))
    save_json(run / "evaluation_report.json", report)
    save_json(dataset_dir(cfg, args.dataset) / "evaluation.json", report)
    groups.to_csv(dataset_dir(cfg, args.dataset) / "group_comparison.csv", index=False)
    print(json.dumps({k: comparison[k] for k in ("n_scored", "n_flagged_statistical", "n_flagged_isolation_forest",
                                                 "flag_agreement", "rank_correlation")}, indent=2))
    print(f"Run: {run}")
    return 0


def cmd_annotate_export(args) -> int:
    from .evaluation import export_annotation_sample
    from .storage import load_table

    cfg = _cfg(args)
    h = load_table(cfg, args.dataset, "hearings")
    if h.empty:
        raise ValueError("Dataset has no per-hearing records; hearing annotation is not applicable.")
    sample = export_annotation_sample(h, args.n, args.seed, args.show_suggestion)
    out = Path(args.out) if args.out else resolve_path(cfg, "annotations_dir") / f"{args.dataset}_to_annotate.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False)
    print(f"Wrote {len(sample)} rows for annotation: {out}")
    return 0


def cmd_review_export(args) -> int:
    from .evaluation import export_review_sample
    from .storage import load_table

    cfg = _cfg(args)
    sample = export_review_sample(load_table(cfg, args.dataset, "anomalies"), load_table(cfg, args.dataset, "hearings"),
                                  args.n or cfg["evaluation"]["review_sample_size"], seed=args.seed)
    out = Path(args.out) if args.out else resolve_path(cfg, "annotations_dir") / f"{args.dataset}_anomaly_review.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False)
    print(f"Wrote {len(sample)} cases for human review: {out}")
    return 0


def cmd_review_evaluate(args) -> int:
    from .evaluation import evaluate_review

    print(json.dumps(evaluate_review(read_table(args.file)), indent=2))
    return 0


def cmd_build_site(args) -> int:
    from .public.build import build_site_data

    cfg = _cfg(args)
    meta = build_site_data(args.extracts, args.out, cfg, min_n=args.min_n)
    print(json.dumps(meta["totals"], indent=2))
    print(f"Site data written to {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tareekh", description="Tareekh Radar research pipeline")
    p.add_argument("--config", default=None, help="YAML merged over config/default.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("ddl-extract", help="Convert a DDL cases_clean_<year>.dta file into the data contract")
    s.add_argument("--dta", required=True)
    s.add_argument("--keys-dir", default=None, help="Directory with DDL key .tab files (default: next to --dta)")
    s.add_argument("--out", required=True)
    s.add_argument("--states", default=None, help="Comma-separated 2-digit state codes, e.g. 26")
    s.add_argument("--districts", default=None, help="Comma-separated SS-DD codes, e.g. 26-01")
    s.add_argument("--name", default=None)
    s.set_defaults(func=cmd_ddl_extract)

    s = sub.add_parser("build-site", help="Build public Case Clock aggregates (JSON) from DDL extracts")
    s.add_argument("--extracts", nargs="+", required=True, help="cases.parquet files from ddl-extract")
    s.add_argument("--out", default="site/data")
    s.add_argument("--min-n", type=int, default=30, help="Suppress groups with fewer cases")
    s.set_defaults(func=cmd_build_site)

    s = sub.add_parser("process", help="Load, validate, clean, (classify,) featurize and score a dataset")
    s.add_argument("--cases", required=True)
    s.add_argument("--hearings", default=None, help="Per-hearing file (omit for case-level sources)")
    s.add_argument("--mapping", default=None)
    s.add_argument("--name", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--human-labels", default=None, help="Completed hearing annotation CSV; overrides automatic labels")
    s.add_argument("--rules-only", action="store_true")
    s.add_argument("--reference-date", default=None, help="Snapshot date for pending cases (YYYY-MM-DD)")
    s.set_defaults(func=cmd_process)

    s = sub.add_parser("train-classifier", help="Train/evaluate TF-IDF+LogReg vs rules on human-labelled hearings")
    s.add_argument("--labels", required=True)
    s.add_argument("--label-col", default="human_label")
    s.add_argument("--text-col", default="text")
    s.add_argument("--model", default=None)
    s.set_defaults(func=cmd_train_classifier)

    s = sub.add_parser("evaluate", help="Method comparison, group comparison, sensitivity analysis")
    s.add_argument("--dataset", required=True)
    s.add_argument("--review-file", default=None, help="Completed anomaly review CSV (human verdicts)")
    s.add_argument("--skip-sensitivity", action="store_true")
    s.set_defaults(func=cmd_evaluate)

    s = sub.add_parser("annotate-export", help="Export a stratified hearing sample for human labelling")
    s.add_argument("--dataset", required=True)
    s.add_argument("--n", type=int, default=300)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--show-suggestion", action="store_true")
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_annotate_export)

    s = sub.add_parser("review-export", help="Export top flagged + random unflagged cases for blind human review")
    s.add_argument("--dataset", required=True)
    s.add_argument("--n", type=int, default=None)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_review_export)

    s = sub.add_parser("review-evaluate", help="Summarise a completed anomaly review file")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_review_evaluate)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (IngestionError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
