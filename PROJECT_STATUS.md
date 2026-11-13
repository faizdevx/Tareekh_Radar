# Project status

_Last updated: 2026-11-13_

## Completed
- Repository inspected. It contained only a one-line README. The modular package `tareekh_radar/` was built from scratch.
- Data contracts (`schemas.py`) and configuration with validation and a config hash (`config/default.yaml`).
- **Real-data adapter** for the DDL eCourts case data (Harvard Dataverse `doi:10.7910/DVN/GHLGSW`, CC0). It streams the 3.5 GB `.dta` file, decodes the code keys and never reads names or CNR.
- Ingestion (CSV/Excel/JSON/Parquet, column mapping, SHA-256 provenance), validation, and cleaning (explicit date formats, out-of-range years, duplicate logs, chronology flags, status inference, quality report).
- Pseudonymisation (HMAC) with a local-only id map.
- Hearing event classification: configurable rules with priority, negation and conflict→UNKNOWN; TF-IDF + LogReg baseline with abstention; human overrides; decision log; annotation workflow; grouped hold-out evaluation.
- Features: hearing-level (rates, conservative and upper-bound streaks, stage returns, intervals, days since substantive progress) and case-level (duration, days since last listing, days to first listing, next-listing gap). Unavailable metrics are null with reasons.
- Anomaly engine: hierarchical peer groups (same case type, same status), vectorised robust z and percentiles, flags, severity, structured explanations with legitimate explanations and supporting records, data-quality marker on flags, Isolation Forest comparison.
- Evaluation: method comparison, court concentration, blind human-review export with controls, review metrics, sensitivity analysis, group comparison, per-run experiment directories.
- FastAPI service and a Streamlit app with five modules, all verified rendering on the real Delhi dataset.
- 44 automated tests (pytest), all passing.
- Documentation in `docs/`.

## Reference run (real data)
- DDL `cases_clean_2010`: 4,281,327 cases extracted (all states). Processed scope: **Delhi, 94,972 cases**.
- Date quality: 422 invalid or out-of-range last-listing dates, 138 decisions before filing, 862 first listings before filing, 488 listings more than 31 days after disposal, 170 cases with undetermined status.
- 94,389 cases scored; 3,727 flagged (2,008 high, 821 medium, 898 low); 48 of the flags are on records with quality issues.
- Contributing features among flags: case_age_days 1,935, days_to_first_listing 1,929, next_listing_gap 73, days_since_last_listing 42.
- Statistical vs Isolation Forest: Spearman 0.58, 671 cases flagged by both.

## Pending
- **Human validation** of the top flags and the controls (`review-export`). No precision figure exists until this is done.
- **Hearing-level data** (DAKSH) must be requested by the researcher. Once it arrives, verify `config/mappings/daksh_template.yaml` against the real headers, annotate hearings, and train and evaluate the classifier on human labels.
- Processing all states (4.28M cases) works in principle but has not been timed end to end. Extraction of all states took about 6 minutes; the Delhi pipeline took about 47 seconds.
- Optional: check `days_to_first_listing` outliers against eCourts migration/entry practice (see limitations).

## Known issues
- Heavy-tailed durations give very large robust z values. Severity is ordinal only.
- 1,929 Delhi flags involve a very late recorded first listing; 1,718 of them are disposed cases. For 15.9% of those 1,718, the first listing falls within 31 days of the decision, which suggests late data entry rather than a real delay. All of them need human review.
- Streamlit's per-page rerun reloads the dataset view from cache. The first load of a large dataset takes several seconds.

## Data limitations
- DDL has no per-hearing history, so adjournment and non-progress metrics are unavailable in case mode.
- The snapshot date is approximated (2021-02-02 for Delhi 2010).
- NJDG and eCourts portals are not used (CAPTCHA; no bulk permission).

## Implementation decisions
- **No synthetic data anywhere.** An early generator was removed at the user's request. Unit tests use small hand-written fixtures under `tests/` only.
- Case types are normalised by spelling only, because abbreviations differ by state.
- Pending and disposed cases are never compared. Every peer level includes the case type or category.
- UNKNOWN never counts as an adjournment. Missing text is never classified by ML.
- Data completeness is reported separately from the anomaly score, never folded into it.
- Hearing classification ignores `next_hearing_purpose` because it describes the next listing.
