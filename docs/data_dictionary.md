# Data dictionary

Types: `string`, `date` (parsed from explicit formats; invalid → null with a status column), `int`, `float`, `bool`. Fields a source does not provide stay null. They are never filled with invented values.

## cases

| Field | Type | Req. | Description | DDL source |
|---|---|---|---|---|
| case_id | string | yes | Source case id. **Pseudonymised** in outputs (`C-XXXXXXXXXX`). | `ddl_case_id` |
| court_id | string | yes | Court establishment code | `state-district-court` |
| court_name | string | | Court name | `court_name` |
| case_type | string | yes | Normalised (orthographic key, upper case); raw kept in `case_type_raw` | `type_name` → key |
| filing_date | date | | Filing/registration date | `date_of_filing` |
| disposal_date | date | | Decision date | `date_of_decision` |
| case_status | string | | `PENDING`, `DISPOSED` or `UNKNOWN` (inferred only from unambiguous evidence) | derived |
| source_reference | string | | Provenance pointer | `ddl:<doi>/<file>#ddl_case_id=<pid>` |
| first_listing_date | date | | First listing | `date_first_list` |
| last_listing_date | date | | Last recorded listing | `date_last_list` |
| next_listing_date | date | | Next scheduled listing at snapshot | `date_next_list` |
| current_purpose | string | | Purpose of latest listing (raw); normalised to `current_purpose_stage` | `purpose_name` → key |
| disposal_nature | string | | Nature of disposal | `disp_name` → key (`disposition var missing` → null) |
| case_category | string | | `CRIMINAL` / `CIVIL` | `criminal` |
| state_code, state_name, district_id, district_name | string | | Geography | `state*`, `district*` |
| *_raw, *_status | | | Original text and parse status (`ok`, `missing`, `invalid`, `out_of_range`, `before_filing`) for each date | |
| data_quality_status | string | | Pipe-separated case flags (see below) or `ok` | |
| filing_cohort | string | | Filing year (bucket size from config) | |

Case flags: `<date>_invalid`, `disposal_before_filing`, `first_listing_before_filing`, `last_listing_before_first`, `listing_after_disposal` (more than 31 days after decision), `next_listing_before_last`, `status_undetermined`.

## hearings (hearing-level sources only)

| Field | Type | Req. | Description |
|---|---|---|---|
| hearing_id | string | | Source id; generated as `<case_id>#r<row>` when absent |
| case_id | string | yes | FK → cases |
| hearing_date | date | yes | Listing/business date |
| hearing_stage | string | | Stage at hearing; normalised to `stage_norm` |
| last_action, last_order | string | | What happened (used for classification) |
| next_hearing_purpose | string | | Purpose of the *next* listing (deliberately **not** used to classify this hearing) |
| source_reference | string | | Provenance |
| data_quality_status | string | | `missing_date`, `invalid_date`, `date_out_of_range`, `missing_description`, `case_not_in_cases_table`, `before_filing_date`, `after_disposal_date`, `multiple_entries_same_date`, `source_order_not_chronological` |
| event_class | string | | `ADJOURNMENT`, `PROCEDURAL_PROGRESS`, `SUBSTANTIVE_PROGRESS`, `UNKNOWN` |
| event_confidence, event_method, event_rule_id, event_subtype, event_reason | | | Classification audit trail (`decision_log` table) |

## features / analysis results (one row per case)

| Field | Mode | Definition |
|---|---|---|
| total_hearings | hearing | Hearing records after de-duplication (including undated) |
| confirmed_adjournments | hearing | Count of `ADJOURNMENT` events (UNKNOWN never counted) |
| procedural_progress_events, substantive_progress_events, unknown_events | hearing | Counts by class |
| adjournment_rate | hearing | adjournments / total_hearings; null if fewer than `min_hearings_for_rates` |
| adjournment_rate_known | hearing | adjournments / non-UNKNOWN events |
| non_progress_streak | hearing | Trailing run of adjournments |
| max_non_progress_streak | hearing | Longest run of consecutive adjournments; UNKNOWN breaks the run |
| max_non_progress_streak_upper | hearing | Same, but UNKNOWN does not break the run (upper bound) |
| repeated_stage_count | hearing | Returns to a previously left recorded stage |
| median_hearing_interval, maximum_hearing_gap | hearing | Days between distinct dated hearings |
| days_since_last_substantive | hearing | Observation end − last substantive event (basis recorded) |
| unknown_record_percentage | hearing | 100 × UNKNOWN / total |
| case_age_days | both | Observation end − filing (observation end = decision if disposed, snapshot if pending) |
| days_to_first_listing | case | First listing − filing (null if negative) |
| days_since_last_listing | case | Snapshot − last listing, **pending cases only** |
| next_listing_gap | case | Next listing − last listing, pending only |
| data_completeness | both | Share of applicable fields available (case mode) / share of records dated and classified (hearing mode) |
| eligible, ineligible_reason | both | Whether the case can be scored, and why not |
| unavailable_metrics | both | JSON: metric → reason it is null |
| evidence | hearing | JSON: hearing ids supporting each feature |
| anomaly_score | both | Max one-sided robust z across features vs the peer group (0 if none positive) |
| anomaly_percentile | both | Mid-rank percentile of anomaly_score within the peer group |
| `<feature>_z`, `<feature>_pct`, `<feature>_peer_median/q1/q3/n` | both | Per-feature peer statistics |
| peer_level, peer_group_key, peer_group_size | both | Peer definition used |
| flagged, severity, contributing_features | both | Flag decision (see methodology) |
| flag_has_quality_issue | both | Flagged **and** the case record has quality flags |
| anomaly_explanation, anomaly_explanation_json | both | Human-readable summary and full structured explanation |
| score_status | both | `scored`, `no_comparable_peer_group`, `ineligible:<reason>` |
| if_score, if_flag, if_status | both | Isolation Forest (experimental) |
