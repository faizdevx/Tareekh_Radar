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
| `purposes.json` | 400 most common recorded hearing purposes ("stage") among pending cases, normalised, with counts; used by the order-sheet decoder |

## Statistics per group (`group_stats`)
- `time_to_decision_days.p50/p75/p90`: Kaplan–Meier quantiles of filing → decision. Each pending case is censored at **its own last recorded listing date**, the latest date it is known to have been pending. This is a lower bound, so it can understate delay but never overstate it. Pending cases with no valid last listing are excluded and counted in `n_excluded_bad_dates`. Transferred, committed and converted cases are censored at their disposal date, since they continue elsewhere. If a quantile is not reached within follow-up, it is `null`, shown as "more than {max follow-up}".
- `curve_monthly_share_decided`: 1 − S(t) at each month, used by the delay checker.
- `share_undecided_at_3y`: S(36 months).
- `outcomes`: shares of outcome groups among disposed (not moved) cases with a recorded nature of disposal.
- `days_to_first_listing`: median and p90 of filing → first listing (negative values dropped).
- `next_hearing_gap_days`: p50/p75/p90/p95 of last listing → next scheduled listing among cases pending at the snapshot.
- `pending_next_gap_over_6m_share`: share of pending cases whose next hearing was set more than 182 days after their last one. This metric needs no collection date.
- Groups with `n < min_n` (30) only publish counts (`suppressed: true`).

## Cohort completeness (important)
Records per filing year in the DDL files: 2010 4.28M, 2011 5.21M, 2012 6.40M, 2013 7.56M, 2014 8.87M, 2015 10.48M, 2016 11.35M, 2017 13.07M, 2018 13.72M. Real filings did not triple, so older years appear to be missing many quickly decided cases (likely disposed before the court's records moved to eCourts). Kaplan–Meier corrects for right-censoring, not for this left-truncation, so durations from older cohorts are biased upward. Mitigations: `build-site --min-filing-year` (recommended: 2014), and caveats on the Methodology page and under the by-filing-year chart.

## Help tools (client-side, `site/js/help.js`)
- **Stage decoder**: ordered regex rules (first match wins) over normalised stage text, 21 stages with EN/HI explanations. Measured on the 400 most common recorded purposes, the rules match 95% of pending cases. Unknown abbreviations are not guessed.
- **CNR check**: format only (2-letter state + 2-letter district + 2-digit establishment + 6-digit serial + 4-digit year). No lookup is made.
- **Cost of delay**: hearings ≈ median time to decision ÷ median scheduled gap between hearings (minimum 7 days); cost = hearings × per-day cost × people. Default per-day cost is the DAKSH 2015-16 survey average (civil ₹497 + ₹844, criminal ₹542 + ₹902), editable. The data has no hearing counts, so this is labelled an estimate.
- **Stuck meter**: the gap since the last hearing placed within the p50/p75/p90/p95 gap quantiles (linear interpolation), and the share of similar cases decided by the case's age (from the KM curve).
- **Legal references** (LSA Act s.12; CPC O.VIII r.1 and O.XVII r.1; CrPC 309/BNSS 346; CrPC 125/BNSS 144; NI Act 143/143A; CrPC 436A/BNSS 479; Art. 226/227, BNSS 528; NALSA 15100; eCourts SMS 9766899899) were checked against statutes, NALSA and eCourts pages and are shown as general information, not advice.

## Case diary and deadlines (`site/js/diary.js`)
- Stored only in `localStorage` (`cc-diary-v1`). No account and no server. Export/import is a JSON file; imports are sanitised (known fields only, bounded strings, valid dates, max 200 cases × 2,000 entries).
- Reminders are RFC 5545 all-day events with an alarm 12 hours before, generated in the browser.
- Deadlines: start date + statutory period (calendar months clamped at month end). The start day is excluded (Limitation Act s.12(1)); court holidays (s.4), certified-copy time (s.12(2)) and condonation (s.5) are explained, not computed. Cheque-bounce complaint = notice receipt + 15 days to pay, then one month from the next day (NI Act s.138(c), s.142(1)(b)).

## Accounts and sync (optional)
- Firebase Authentication (email/password with verification, Google) and Cloud Firestore (asia-south1). Documents live at `users/{uid}/cases/{caseId}` with fields `label, cnr, s, d, c, filed, court, entries, updated`.
- Rules (published in the console; keep in sync with `site/js/cloud.js putCase`): owner-only read/delete; create/update only by the owner, only those keys, at most 2,000 entries; all other paths denied.
- Sync: on sign-in (verified email) the account's cases are pulled, sanitised and merged with the device's (`mergeCases`: newer `updated` wins; device-only cases are pushed). Later edits stamp `updated` and push. Deleting a case locally deletes it in the account. Failures leave the device copy intact.
- Delete account: removes every case document, then the login (Firebase may ask for a fresh sign-in; the UI says so).
- The Firebase web config is public by design; protection is the rules, not the key.

## Time left and "Ask an AI" (`logic.js remainingTime`, `ai.js`)
- Time left: with `F(m)` the monthly share decided and age month `a`, the share of still-pending cases decided within `k` more months is `(F(a+k) − F(a)) / (1 − F(a))`. The reported half/9-in-10 are the smallest `k` reaching 0.5/0.9; `null` means not reached within follow-up (shown as "more than"). If fewer than 6 months of follow-up remain after the age, no estimate is given; if under 3% of cases remain pending at that age it is flagged as a rough guide.
- The AI prompt is built from: case type, court, statistics level, case age, gaps, stage text (and its decoded meaning), adjournment counts and hearing count (diary), the real quantiles, outcome shares and the verdict. It tells the model to use only these facts, not to invent numbers and not to predict the outcome, and asks for plain-language explanation, five questions for the lawyer, lawful next steps and the limits of the numbers.
- Sending is always the person's action: edit the preview, tick the consent box, press a button. `?q=` pre-fills ChatGPT and Claude; auto-send is not guaranteed by either, and the answer is not returned to the site. Over 7,000 encoded characters only Copy is offered.

## Layer 1 companion features
- Case documents now also hold `room`, `checks` (document-checklist ticks), `expenses` (date, category, amount, people, note) and `viewers` (up to 5 lowercase emails). All are sanitised on load/import.
- Firestore rules must allow those keys and let a verified email listed in `viewers` read the case (path rule plus a collection-group rule for `/{path=**}/cases/{caseId}`), with a collection-group index on `viewers` for the "shared with me" query.
- OCR: Tesseract.js 7.0.0 (jsDelivr) with `eng`+`hin` best_int data (~3 MB + ~1.4 MB), cached by the service worker after first use. `parseOrderText` finds day-first numeric and named-month dates, picks the date after "next date / put up / fixed for / अगली तारीख / पेशी" (else the latest date) and a purpose the stage decoder recognises. The person always confirms before saving.
- Lok Adalat dates: `prep.js LOK_ADALAT` (NALSA letter L/34/2018-NALSA, 04.12.2025). Update yearly.

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
- Next steps depend on the result (gap, age, case type) and link to the site's help tools and official sites only (eCourts, NALSA).

## Categories
Rules are in `tareekh_radar/categories.py`. Act/section overrides the type name when recognised (NI Act 138 → cheque bounce; CrPC 125 → maintenance; CrPC 436–439 → bail; Motor Vehicles Act → motor accident). Unclear abbreviations stay in "Other / unclear type".

## Not used
The site does not use any live eCourts lookup. The scrapers suggested for this (varun-heman/district-court-api-scraper, openjustice-in/ecourts) were reviewed and **not used**: both work by solving the eCourts CAPTCHA, and one also rotates proxies to avoid rate limits.
