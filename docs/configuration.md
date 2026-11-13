# Configuration

All thresholds live in `config/default.yaml`. To change them, pass a YAML containing only the keys to override:

```bash
python -m tareekh_radar.cli --config my.yaml process ...
```

The Streamlit app reads the same file from the `TAREEKH_CONFIG` env var. The analytical config (everything except `paths`) is hashed into `run_info.config_hash`.

| Section | Keys | Purpose |
|---|---|---|
| `paths` | raw/processed/annotations/models/runs dirs, salt file | Locations (relative to repo root) |
| `privacy` | `pseudonymize`, `salt_env_var`, `pseudonym_prefix/length`, `drop_unmapped_columns` | Pseudonyms and column dropping |
| `dates` | `formats`, `min_valid_date`, `max_valid_date` | Explicit parsing; range validity |
| `cleaning` | `duplicate_keys` | Content-duplicate definition for hearings |
| `case_type_aliases` | canonical → aliases | Optional semantic merging (empty by default; abbreviations vary by state) |
| `stage_patterns` | canonical → regexes | Stage normalisation (first match wins) |
| `classification` | `text_fields`, `rule_min_confidence`, `negation_*`, `ml_min_probability`, `mode`, `ml.*`, `rules[]` | Hearing event classification |
| `features` | `min_hearings_for_rates`, `min_hearings_for_intervals`, `max_unknown_share_for_eligibility`, `reference_date`, `case_reference_date`, `filing_cohort_years` | Feature availability and eligibility |
| `anomaly.modes.<hearing\|case>` | `features{floor, min_abs}`, `peer_levels` | Scored features and peer hierarchy per mode |
| `anomaly` | `min_peer_size`, `z_threshold`, `percentile_threshold`, `severity`, `isolation_forest.*` | Flagging and the comparison model |
| `evaluation` | `top_k`, `sensitivity.*`, `review_sample_size` | Research evaluation |

Validation rules enforced at load:

- `classification.mode` must be one of `rules`, `ml` or `hybrid`.
- Every rule must have an id, category, priority, confidence and patterns.
- Every peer level must include `case_type` or `case_category`.

## Rule format

```yaml
- id: adjournment_party_request
  category: ADJOURNMENT          # one of classification.categories
  priority: 50                   # higher wins on conflict; ties between categories -> UNKNOWN
  confidence: 0.9
  negatable: false               # true: skip match if a negation cue is in/just before it
  subtype: party_request         # optional, shown in explanations
  patterns: ["\\b(time|adjournment)\\b.{0,15}\\b(sought|granted)\\b"]
```

## Mapping files

Mapping files connect a source's columns to the data contract:

```yaml
dataset: {name: my_dataset, is_synthetic: false, level: hearing, source: "...", license: "...", geographic_scope: "...", access_notes: "..."}
cases:    {case_id: CNR_NO, court_id: EST_CODE, case_type: CASE_TYPE, filing_date: DATE_FILED}
hearings: {case_id: CNR_NO, hearing_date: BUSINESS_DATE, hearing_stage: STAGE, last_order: PROCEEDINGS}
```
