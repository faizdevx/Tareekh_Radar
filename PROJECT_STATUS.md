# Project status

_Last updated: 2026-11-14_

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
- 94,389 cases scored; 3,739 flagged (2,004 high, 828 medium, 907 low); 47 of the flags are on records with quality issues.
- Contributing features among flags: case_age_days 1,973, days_to_first_listing 1,929, next_listing_gap 73. days_since_last_listing is not computed, because DDL's collection date is unknown.
- Statistical vs Isolation Forest: Spearman 0.58, 682 cases flagged by both.

## Public site: Case Clock (added 2026-11-14)
- `site/`: static bilingual (EN/हिंदी) site matching the provided mockup. It has an estimator, a delay checker (runs in the browser), district report cards, methodology and about pages. Artwork is original SVG.
- `build-site` aggregates 9,489,980 real cases (filed 2010–2011, 32 states/UTs, 629 districts) into 8.4 MB of JSON. It uses Kaplan–Meier time to decision with pending cases censored at their own last listing, outcome groups, hearing gaps, and suppression under 30 cases.
- Case categories come from a transparent rule set over the recorded type name and act/section (`categories.py`). DDL's `criminal` flag was found to mark only a subset of criminal cases, so it is no longer used as a civil/criminal label.
- Verified in the browser at desktop and mobile widths, in English and Hindi. Tests: 51 pytest, 10 node.
- Reviewed and rejected: two eCourts scrapers suggested for live data, because both solve the eCourts CAPTCHA.
- Filing years 2012–2018 downloaded and extracted (DDL Dataverse). `ddl-extract` now streams chunks to parquet (the 2018 file is 11.8 GB). Site data now covers **80,935,944 cases filed 2010–2018, 32 states/UTs, 632 districts** (11 MB of JSON). The full build takes about 4.5 hours.
- **Cohort bias found**: records per filing year rise from 4,281,327 (2010) to 13,724,299 (2018). Older years appear to be missing quickly disposed cases (likely decided before courts migrated to eCourts), so their durations are biased upward and the by-filing-year chart overstates improvement. This is documented on the site. `build-site --min-filing-year` was added, and the site now uses **cases filed 2014–2018 (57,489,564 cases, 632 districts, 9.9 MB)**. That build takes about 30 minutes.
- Bail: most states decide half of bail applications within about 2 weeks, but Uttar Pradesh and Rajasthan records show medians of years, which suggests applications are closed only when the main case ends. The site shows a caveat when bail medians exceed 6 months.
- **Help tools** added (`site/js/help.js`): CNR finder and format check, order-sheet stage decoder (21 stages, EN/HI; matches 95% of pending cases' recorded stage text, using `purposes.json` built from real records), questions for your lawyer by stage (print / WhatsApp / copy), cost-of-delay estimate (DAKSH 2015-16 per-day costs, editable), free legal aid (LSA Act s.12) and statutory time limits with real district medians, and a "stuck meter" plus tailored next steps on the delay check. Legal references were checked against statutes, NALSA and eCourts pages.
- GitHub Pages enabled: https://faizdevx.github.io/Tareekh_Radar/
- Tests: 53 pytest, 15 node.
- **Case diary + reminders + deadline calculator** (`site/js/diary.js`): local-only storage (no login by decision: no server holds anyone's case data), import sanitised as a trust boundary, .ics reminders, printable summary, stuck check against real data; 12 statutory deadlines verified against the Limitation Act, NI Act, CPC, MV Act, CPA 2019 and RBI. Tests: 21 node.
- **Optional sign-in and cloud sync** (`site/js/cloud.js`, `firebase-config.js`): Firebase project `case-clock` (Spark plan, no billing). Email/password (verification required before anything syncs, 8+ char password policy enforced, enumeration protection on) and Google sign-in; `faizdevx.github.io` authorised; Firestore in Mumbai (asia-south1), production mode. Published rules: each user may read/write only `users/{uid}/cases/*`, with a key allowlist and an entries cap; everything else denied. Local-first: signed-out use is unchanged; sign-in merges device and account cases (newer `updated` wins), then pushes changes. Consent checkbox, privacy notice page (draft, not lawyer-reviewed) and in-app delete-account-and-data. The web config in the repo is public by design. Not yet exercised end to end with a real account.
- **Time left + Ask an AI** (`remainingTime` in `logic.js`, `ai.js`): conditional time-to-decision from the existing monthly KM curves; shown on the delay check and diary case pages. The AI feature is client-only: facts-only prompt, user-editable preview, consent tick, then `chatgpt.com/?q=` / `claude.ai/new?q=` pre-fill links (neither is documented to auto-send, so the user presses Send; the answer stays in that app) or Copy. Links are withheld above 7,000 encoded characters. Prompt excludes CNR, names and notes. Tests: 27 node. In-site answers via an API proxy (Cloudflare Worker, signed-in users, rate limit) were scoped but not built; they need an AI provider key and billing.
- **Layer 1 companion features** (`prep.js`, `voice.js`, `ocr.js`, `sw.js`, `manifest.webmanifest`): hearing-day mode, order-sheet OCR (Tesseract.js 7.0.0 from jsDelivr, eng+hin, local only; parser tested on English/Hindi date formats; a real OCR run on a generated order sheet extracted the hearing date, next date and purpose), read-aloud (speechSynthesis) and dictation (Web Speech API, disclosed as server-based in Chrome), WhatsApp reminder links, document checklists per case type, expense tracker (7 categories, people count; DAKSH 2015-16 benchmark, unadjusted), printable case summary, Settlement Options (NALSA 2026 National Lok Adalat dates verified; LSA Act s.21 finality and s.19(5) non-compoundable bar), read-only family sharing by email (needs updated Firestore rules + collection-group index), PWA install + offline cache. Research claims checked before use: the "inflation-adjusted DAKSH" figures in an external summary are not DAKSH's own and were not used.
- **Simpler 3D UI** for low-literacy users: home opens with 10 big picture tiles (2-4 word labels), raised pressable buttons/cards and sunken inputs (CSS only, no WebGL, so cheap phones stay fast), 18px base text and 52px tap targets, floating read-aloud button on every page, 5-item top menu (Method/About in the footer) and 4-item bottom bar, case-page extras folded into one-tap sections. No feature removed.
- **Layers 2/3/5/6 (first batch)** (`layer2.js`, `build_rankings`): before-court guide, legal-aid checker + letter, 4 notice drafts, journeys, multi-alarm deadline reminders, intake sheet, district poster, quiz, agenda/clash view, rankings.json (built from published district JSON, no re-extract), court story of the month, open data page, bigger-text/high-contrast toggles. Facts checked before use: consumer jurisdiction ₹50 lakh (2021 Rules) and nil fee up to ₹5 lakh; NCH 1915 / 1800-11-4000 / WhatsApp 8800001915; RTI ₹10, 30 days/48 h, BPL exempt, first appeal 30 days; BNSS 173(1)/173(4)/175(3) (affidavit + prior SP complaint); s.138 notice by registered/speed post; LSA s.13(2) income affidavit; NALSA online application; SAMADHAN active; Mediation Act pre-litigation provisions treated as not in force; rent rules state-specific (no rent template). First load ≈135 KB gzipped.
- **India delay map** (`geo.py`, `build-map`): DataMeet Census-2011 districts (CC BY 2.5 IN; 641 shapes incl. the official-outline placeholder for areas without data), pure-Python Douglas–Peucker simplification to 389 KB (145 KB gzipped), SVG paths in the browser. Name matching (exact, aliases for renames, direction-safe fuzzy, name-only only for Telangana/Ladakh splits): 588 of 628 eCourts districts on the map; the other 40 are districts created after 2011 or non-geographic courts (audit in `india_map_match.json`).
- Not built yet (need design, data or partners): volunteer mode with write access to others' cases (16), client update tool for lawyers (20), stage-level gap benchmarks (22), policy simulator (27), DAKSH partnership (28, outreach), more languages (30, translators), in-site AI (32, API key + billing).
- Pending: human review of the category mapping, stage glossary, deadline list, checklists and privacy notice; first real sign-in and family-sharing test with two accounts; confirm the ChatGPT/Claude pre-fill links in a signed-in browser; add 2027 National Lok Adalat dates when NALSA publishes them.

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
- DDL's collection date is not published (pending records cluster in early 2019, some updated in 2020). Pending cases are observed up to their own last listing, which is a lower bound.
- NJDG and eCourts portals are not used (CAPTCHA; no bulk permission).

## Implementation decisions
- **No synthetic data anywhere.** An early generator was removed at the user's request. Unit tests use small hand-written fixtures under `tests/` only.
- Case types are normalised by spelling only, because abbreviations differ by state.
- Pending and disposed cases are never compared. Every peer level includes the case type or category.
- UNKNOWN never counts as an adjournment. Missing text is never classified by ML.
- Data completeness is reported separately from the anomaly score, never folded into it.
- Hearing classification ignores `next_hearing_purpose` because it describes the next listing.
