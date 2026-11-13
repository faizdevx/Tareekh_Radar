# Annotations (human labels)

Completed annotation and review files go here. The directory is gitignored except for this README, so files containing case information are never committed.

## Hearing event labels (`annotate-export`)
Fill `human_label` with one of `ADJOURNMENT`, `PROCEDURAL_PROGRESS`, `SUBSTANTIVE_PROGRESS` or `UNKNOWN`. Also fill `annotator` and, optionally, `notes`.

- **ADJOURNMENT**: an explicit postponement, rescheduling or deferment.
- **PROCEDURAL_PROGRESS**: filing, appearance, notice or summons issued/served, documents submitted, other procedural steps.
- **SUBSTANTIVE_PROGRESS**: evidence recorded, arguments heard, judicial orders, charges or issues framed, disposal.
- **UNKNOWN**: missing, ambiguous or unreliable text. **Use this when unsure.** Never label missing text as an adjournment.

Double-annotate a subset (same `hearing_id`, different `annotator`) to get Cohen's kappa.

## Anomaly review (`review-export`)
Hide the `sample_group` column while reviewing. For each case, set `reviewer_verdict` to one of:

- `pattern_confirmed`: the record shows the unusual progression pattern.
- `legitimate_explanation`: the pattern is real but has a legitimate procedural explanation.
- `data_artifact`: the pattern comes from wrong or missing data.
- `not_unusual`: no unusual pattern.

Verdicts concern the **record**, never the conduct of any person.
