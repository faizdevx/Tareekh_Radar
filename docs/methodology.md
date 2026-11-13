# Methodology

## 1. Cleaning

- **Dates:** parsed only with the explicit formats in `dates.formats`, tried in order (day-first Indian formats first). Unparseable values become `invalid`. Values before `min_valid_date` or after the run date become `out_of_range`; DDL contains years such as 0001 and 9201. The raw value is kept.
- **Duplicates:** repeated `case_id`; repeated `hearing_id`; identical (case, date, normalised description). Removed rows are kept in `duplicates.parquet` with a reason. Several different entries on the same date are kept and flagged.
- **Case types:** orthographic normalisation only (`O.S.` = `os`). Abbreviations mean different things in different states, so there is no semantic merging unless configured.
- **Stages:** regex map to canonical stages (`config.stage_patterns`). Unmatched text becomes `OTHER`, missing text becomes `UNKNOWN`.
- **Status:** `DISPOSED` only with a valid decision date (or explicit status text), `PENDING` only when there is no decision date and no disposal nature, otherwise `UNKNOWN`.
- **Chronology:** flags listed in the data dictionary. Nothing is dropped silently.

## 2. Hearing event classification (hearing-level sources)

1. **Rules** (`classification.rules`): regexes over the lower-cased `last_action | last_order`. Each rule has a category, priority and confidence. *Negation* cues (`not`, `no`, …) inside a match or up to 8 characters before it cancel progress rules. The highest-priority category wins. Equal-priority conflicts give UNKNOWN. Several hits in the same category combine as `1 − Π(1 − c)`. A result below `rule_min_confidence` stays UNKNOWN; for example, a bare "put up for evidence" records a date but not why nothing happened.
2. **Missing or empty text is always UNKNOWN** (`missing_description`), never an adjournment. A final guard enforces this after ML and human steps.
3. **ML baseline:** TF-IDF (1–2-grams, sublinear) + class-balanced logistic regression. It abstains (UNKNOWN) below `ml_min_probability`. In `hybrid` mode, ML only fills rule-UNKNOWN events that have text.
4. **Human labels** from the annotation workflow override automatic labels (`event_method = human`).
5. Every decision is logged: class, confidence, method, rule id, subtype and reason.

*Next-hearing purpose describes the next listing, so it is not used to classify the current hearing.*

## 3. Features

See the [data dictionary](data_dictionary.md) for exact definitions. Conventions:

- Chronological order is (date, source row). Undated records count towards totals but not towards intervals or streaks.
- Procedural progress counts as progress. Routine procedural events are not treated as meaningless.
- With too few observations, a metric is **null with a reason** (`unavailable_metrics`), never 0.
- Streaks have a conservative version (UNKNOWN breaks a streak) and an upper bound, which brackets the effect of missing descriptions.
- Case-level snapshot date: `features.case_reference_date`, or by default the latest valid last-listing/decision date in the dataset (Delhi 2010: 2021-02-02).

## 4. Anomaly detection

### Peer groups

Each eligible case is compared with eligible cases from the same dataset at the most specific level in `anomaly.modes.<mode>.peer_levels` that has at least `min_peer_size` (30) cases. Every level contains the case type (or the coarse category at the last level). In case mode every level also contains the status, so pending and disposed cases are never compared. Cases with no such group are reported as `no_comparable_peer_group` and are not scored.

### Statistical baseline (primary)

For each feature *x* and peer group *G*:

- median *m*, quartiles *q1*, *q3*, MAD
- scale *s* = max(1.4826·MAD, (q3 − q1)/1.349, floor)
- robust z = (x − m) / s, which is one-sided: only high values are unusual
- percentile = (#{G < x} + ½·#{G = x}) / |G|

A feature **contributes** when z ≥ `z_threshold` (3.5), percentile ≥ `percentile_threshold` (0.95) **and** x ≥ `min_abs`. The `min_abs` floor stops trivially small values from flagging; for example, case duration must be at least 3 years. `anomaly_score` is the largest positive z. Severity uses the largest contributing z: low ≥ 3.5, medium ≥ 5, high ≥ 7.

Data completeness is **not** part of the score. It is reported next to it, and `flag_has_quality_issue` marks flags on records with inconsistent dates.

### Isolation Forest (experimental)

The model is fitted separately per case status. It uses features present in at least 50% of that status group. Features are robust-scaled within case type (median/IQR with the same floors), and fitting uses at most 200k sampled rows. `if_flag` marks the top `top_fraction` of scores. It is a comparison model only and is not assumed to be better.

### Explanations

Each flagged case gets a structured explanation with:

- the score and peer percentile
- each contributing feature with its value, peer median, IQR, z and percentile, written as a sentence
- possible legitimate explanations for that feature
- supporting records: hearing ids, or the source record and the dates used
- the peer-group definition and size
- data-completeness details and quality flags
- model limitations and the disclaimer

Explanations for unflagged cases are built on demand by the app and API. No probability of misconduct is ever computed.
