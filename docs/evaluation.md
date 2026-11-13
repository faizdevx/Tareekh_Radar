# Evaluation methodology

No performance number in this project is invented. Metrics need either the processed real data (method comparisons, sensitivity) or human labels (classifier quality, precision of flags).

## Research questions

1. Can repeated non-progress patterns be identified from judicial hearing histories? This needs hearing-level data (DAKSH). With case-level DDL data, only duration, dormancy and listing-gap patterns can be studied.
2. Does peer-group normalisation give more meaningful rankings than raw counts? This is measured by the rank correlation and top-k overlap between the statistical score and raw `case_age_days` / adjournment counts, by how concentrated the top-ranked cases are in single courts, and finally by blind human review of both rankings.
3. How does incomplete documentation affect detection? This is measured by sensitivity analysis.
4. Does explainable statistical detection compare well with unsupervised ML? This is measured by flag agreement, rank correlation, top-k overlap and labelled AUC/AP once human review exists.

## Classifier evaluation (hearing-level data)

- `annotate-export` draws a sample stratified by rule class. Suggestions are hidden by default to avoid anchoring.
- `train-classifier` splits with `GroupShuffleSplit` by **normalised text** (default) or by case. Identical descriptions therefore never sit on both sides, and the report states `test_texts_seen_in_training_pct`.
- It reports precision, recall, F1 per class, macro F1, the confusion matrix, class distributions, abstention rate, and `true_unknown_predicted_adjournment` (must be 0 for the rules) for **rules, ML and hybrid**.
- Cohen's kappa is reported when hearings have two annotators.
- The deployed model is refit on all labels. The reported numbers always come from the hold-out split.

## Anomaly evaluation

- `compare_anomaly_methods`: Spearman correlations and top-k Jaccard overlaps between the statistical score, Isolation Forest and raw baselines; flag agreement; court concentration of the top 500.
- **Human review** (`review-export`): the top-n flagged cases plus *n* random scored-but-unflagged controls, shuffled. Scores and explanations are hidden. Verdicts are `pattern_confirmed`, `legitimate_explanation`, `data_artifact` or `not_unusual`. The pattern-present rate on flagged cases estimates precision. On controls it estimates the miss rate. `data_artifact` measures how often flags come from bad records. False-positive and false-negative case ids are listed.
- **Sensitivity**: random record dropping, plus masking of listing dates (case mode) or descriptions (hearing mode), at 10–30%, repeated. It reports scored and flagged counts, Spearman correlation with the baseline, top-10 Jaccard, the share of baseline flags kept and the number of new flags.
- **Group comparison**: flag rates and median scores per court and per case type.

## Reference results (real data: DDL Delhi, filed 2010)

From `python -m tareekh_radar.cli evaluate --dataset ddl_2010_delhi`. These are unlabelled diagnostics, not accuracy figures:

- 94,389 cases scored. 3,727 statistical flags and 931 Isolation Forest flags (top 1%); 671 cases flagged by both.
- Spearman: statistical vs IF 0.58; statistical vs raw case age 0.51; statistical vs raw days since last listing 0.37.
- Top-50 overlap with raw case-age ranking: 0.0. Peer normalisation changes which cases rank highest.
- Sensitivity: with 30% of case records dropped, Spearman vs baseline is 0.98 and 91–92% of baseline flags are kept. With 30% of listing dates masked, Spearman is 0.98 but only 64–65% of baseline flags are kept. Flags depend more on listing-date completeness than on the sample size.
- Human validation: **not yet done**. No precision figure exists until reviewers complete the review sheet.
