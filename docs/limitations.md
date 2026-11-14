# Known limitations and assumptions

## Interpretation
- Results are **statistical deviations within one dataset**. They are not legal or official standards and are **not evidence of misconduct**. Every unusual pattern may have legitimate explanations, which the app lists for each feature.
- Scores are not probabilities.

## Data (DDL case-level)
- There is **no per-hearing history**. Adjournments, non-progress streaks and stage loops cannot be observed; they are shown as unavailable.
- The collection date of each record is not published. Pending cases' last listings cluster in early 2019, with some updates in 2020. By default, a pending case is therefore observed only up to its own last listing. Durations are lower bounds, and "days since last listing" is unavailable unless `features.case_reference_date` is set to a known collection date.
- Dates are as recorded in eCourts at scrape time. Some are impossible (years 0001, 9201) or inconsistent (listing after disposal, first listing before filing). They are flagged and excluded from the affected features, and flags on such records are marked `flag_has_quality_issue`.
- A very late `date_first_list` on a disposed case may reflect data-entry or migration into the case-information system rather than a real delay. This feature contributes to 1,929 of the 3,739 Delhi 2010 flags. In 15.9% of the disposed ones, the first listing is within 31 days of the decision. These need human review.
- `case_status` follows DDL's convention that a missing decision date means pending at the snapshot. Cases with a disposal nature but no date are left `UNKNOWN`.
- Case types are normalised only by spelling. Local abbreviations are not mapped to national categories.
- The replication release covers filing years 2010–2018 and only the courts DDL collected.

## Method
- Peer groups use only cases in the processed scope. Small courts fall back to coarser levels (district, then state), recorded in `peer_level`.
- Robust z on heavy-tailed duration data gives very large values (z > 100) for extreme cases. Severity is ordinal, not calibrated.
- The Isolation Forest is unsupervised and fitted on scaled features. Its flags are a fixed top fraction, not a calibrated threshold.
- Hearing-level classification rules were written from general Indian court terminology. They must be checked against human annotations of the actual source before results are trusted.
- No human validation has been done yet, so precision and recall of the flags are unknown.

## Privacy
- Pseudonyms are keyed hashes. The re-identification map (`id_map.LOCAL_ONLY.parquet`) and the salt stay local and must not be shared.
- Free-text order fields in hearing-level sources may contain names. The project does not run name redaction on free text.
