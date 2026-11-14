# Public site (Case Clock): data and methods

## Pipeline
1. `ddl-extract`: the DDL `cases_clean_<year>.dta` file is converted to `cases.parquet`. All states are kept, along with the act/section columns. Names and CNR are never read.
2. `build-site`: for each state, the data goes through `clean_cases` (explicit date parsing, invalid and out-of-range dates removed, status inference). Categories and outcome groups are then assigned, and JSON aggregates are written.

| File | Contents |
|---|---|
| `meta.json` | coverage, licence, citation, categories, outcome groups, states → districts list, home-page example |
| `national.json` | per category, pooled across states |
| `states/<code>.json` | state summary, per category, district comparison list |
| `districts/<id>.json` | district summary (incl. by filing year), per category |
| `category_mapping.json` | top 1,500 recorded case types → category, with counts (audit) |

## Statistics per group (`group_stats`)
- `time_to_decision_days.p50/p75/p90`: Kaplan–Meier quantiles of filing → decision. Each pending case is censored at **its own last recorded listing date**, the latest date it is known to have been pending. This is a lower bound, so it can understate delay but never overstate it. Pending cases with no valid last listing are excluded and counted in `n_excluded_bad_dates`. Transferred, committed and converted cases are censored at their disposal date, since they continue elsewhere. If a quantile is not reached within follow-up, it is `null`, shown as "more than {max follow-up}".
- `curve_monthly_share_decided`: 1 − S(t) at each month, used by the delay checker.
- `share_undecided_at_3y`: S(36 months).
- `outcomes`: shares of outcome groups among disposed (not moved) cases with a recorded nature of disposal.
- `days_to_first_listing`: median and p90 of filing → first listing (negative values dropped).
- `next_hearing_gap_days`: p50/p75/p90/p95 of last listing → next scheduled listing among cases pending at the snapshot.
- `pending_next_gap_over_6m_share`: share of pending cases whose next hearing was set more than 182 days after their last one. This metric needs no collection date.
- Groups with `n < min_n` (30) only publish counts (`suppressed: true`).

## Collection date (why there is no "today" in the historical data)
DDL does not publish when each record was collected. In the 2010–2011 files, pending cases' last listings cluster around **Jan–Feb 2019**, and a minority were updated in **2020**. A single snapshot date would therefore be wrong for most records. An earlier version used the 99.9th percentile of listing dates (about Sept 2020), and it made 81% of Maharashtra's pending cases look unlisted for over a year. The fix is that nothing in the public statistics depends on a collection date:
- durations of pending cases end at their own last listing;
- the dormancy metric uses the scheduled gap from last listing to next listing.
`snapshot_date` in the JSON is only the median last listing of pending cases, used for the "records last updated around …" note.

## Delay checker (client-side, `site/js/logic.js`)
- It uses the district × category statistics. If that group is suppressed, it falls back to the state, then to national, and says which it used.
- Verdict levels:
  - **longer**: days since the last hearing exceed the p95 hearing gap, or the next date is further than p95, or fewer than 10% of similar cases were undecided at this case's age.
  - **somewhat**: days since the last hearing exceed p75, or fewer than 25% of similar cases were undecided at this case's age.
  - **usual**: neither of the above.
  - **insufficient**: no comparable statistics.
- Next steps link only to official sites: eCourts services and NALSA (legal aid, Lok Adalat).

## Categories
Rules are in `tareekh_radar/categories.py`. Act/section overrides the type name when recognised (NI Act 138 → cheque bounce; CrPC 125 → maintenance; CrPC 436–439 → bail; Motor Vehicles Act → motor accident). Unclear abbreviations stay in "Other / unclear type".

## Not used
The site does not use any live eCourts lookup. The scrapers suggested for this (varun-heman/district-court-api-scraper, openjustice-in/ecourts) were reviewed and **not used**: both work by solving the eCourts CAPTCHA, and one also rotates proxies to avoid rate limits.
