# Tareekh Radar

Tareekh Radar is a research tool. It finds **statistically unusual case-progression patterns** in Indian court records, such as very long pendency, long periods without a listing, long delays to first listing, and (where per-hearing data exists) repeated adjournments, non-progress streaks and stage loops. It explains every flag in plain language.

> **What it is not.** The tool reports statistical deviations from comparable cases in the same dataset. An unusual pattern can have legitimate procedural explanations, and it can also be a data error. **Nothing in this project establishes misconduct or responsibility by any judge, lawyer, litigant or court official.**

## Case Clock: the public website (`site/`)

**Case Clock (तारीख घड़ी)** is a free, bilingual (English/हिंदी) static website for litigants. It is built on the same real data:

- **How long will it take?** Historical time to decision (Kaplan–Meier, so pending cases are not dropped) and how cases ended, for a case type in your district.
- **Is my case delayed?** You enter your filing, last-hearing and next-hearing dates, and the site compares them with similar cases. This happens **in your browser; your dates are never sent anywhere.** It also links to official next steps: eCourts status, free legal aid (NALSA/DLSA), Lok Adalat.
- **District report cards**: median time to decision, share of cases undecided after 3 years, long scheduled gaps, and a breakdown by case type.

- **My case diary** (works without an account; stored in the browser, and synced to your account if you sign in with Google or email): log each hearing, what happened, the next date and who asked for adjournments; see whether the case looks stuck against real cases; add hearing dates to the phone calendar (.ics); print a summary; export/import a backup file.
- **How much longer?** For a case already N months old, the real data answers: among similar cases still pending at that age, when were half / 9 in 10 decided (conditional on surviving to that age; "more than X" when the data does not reach it).
- **Ask an AI** (optional, no server): builds a facts-only question from those real numbers, the stage and adjournment counts, shows the exact text for editing, and after a consent tick opens ChatGPT or Claude with the question pre-filled (or copies it for any app). The answer appears in that app; the site never receives it. No CNR, names or diary notes are included.
- **Case companion (layer 1)**: hearing-day mode (court, room, what to carry for the stage, questions to ask, read aloud), order-sheet photo reader (Tesseract.js in the browser; the photo never leaves the phone; you confirm the extracted next date and purpose), voice read-aloud and dictation, WhatsApp reminder text, document checklist per case type, expense tracker against the DAKSH benchmark, one-page case summary / PDF, Settlement Options (Lok Adalat eligibility, real historical shares, next National Lok Adalat, consequences of an award), read-only family sharing, and an installable offline app (service worker).
- **Before court** (layer 2): "Do I need court?" guide (consumer helpline/e-Daakhil, police/Zero FIR, RTI, money owed, family, labour/SAMADHAN, land), free legal aid eligibility checker (LSA Act s.12) with an application letter, notice/letter drafts (cheque-bounce s.138 notice, consumer complaint letter, RTI application, letter to your lawyer; rent left out because it is state-specific), step-by-step journeys with real district figures, and deadline reminders 7 days, 1 day and 12 hours before.
- **For helpers** (layer 3): walk-in intake sheet (one printable page, can be saved as a case), printable A4 district posters, a training quiz built from the glossary and deadlines, and an agenda of this week's hearings with same-day clash warnings.
- **India delay map**: every district coloured by typical time to decision (or share undecided at 3 years) for a chosen case type; tap for details, zoom to a state. District boundaries: DataMeet India (Census 2011), CC BY 2.5 IN, simplified; outline follows India's official boundary claim.
- **Android app** (free, no Play Store): [download case-clock.apk](https://github.com/faizdevx/Tareekh_Radar/releases/latest/download/case-clock.apk). It is a Trusted Web Activity built with PWABuilder: the same site opens full-screen in Chrome, so sign-in, sync and every tool work the same. Needs Chrome; allow "Install unknown apps" when asked. Domain verification: `https://faizdevx.github.io/.well-known/assetlinks.json` (repo `faizdevx/faizdevx.github.io`).
- **Data** (layer 5): district rankings per case type, an automatic "court story of the month", and an open data page documenting the JSON files. Accessibility: bigger-text and high-contrast switches.
- **Deadline calculator**: last date for cheque-bounce steps (NI Act), written statement, civil/criminal appeals and revisions (Limitation Act), motor accident claims and consumer complaints, with the law cited and a calendar reminder.
- **Help tools** built around problems litigants raise on Indian legal forums: find and check your CNR, decode the order-sheet stage (glossary matched against the 400 most common stages actually recorded for pending cases), questions to ask your lawyer by stage (print/WhatsApp), cost of delay (real durations × DAKSH survey costs), and free legal aid plus the time limits written in law, with the real district figures next to them.

The site uses 57,489,564 real cases filed 2014–2018 across 32 states/UTs and 632 districts (DDL eCourts). Filing years 2010–2013 are extracted but left out: they under-represent quickly decided cases (records per year rise from 4.3M in 2010 to 13.7M in 2018), which biases durations upward. See `build-site --min-filing-year`. Only aggregates are published, and groups under 30 cases are hidden. Run it locally with `python -m http.server 8611 --directory site`. See [site/README.md](site/README.md) and [docs/public_site.md](docs/public_site.md).

## Data: real sources only

The project ships **no data** and **no generated or synthetic records**. All analysis runs on public judicial data that you download yourself.

| Source | Granularity | Status in this project |
|---|---|---|
| **Development Data Lab (DDL) eCourts case data 2010–2018**, Harvard Dataverse `doi:10.7910/DVN/GHLGSW` | one row per case: filing, decision, first/last/next listing dates, purpose, type, disposal | **Supported** (`ddl-extract` adapter). Used for the reference analysis. |
| DAKSH High Court data (case + hearing level) | per hearing | Generic hearing-level pipeline ready. Access is through DAKSH's form or email, which the user must request. |
| NJDG / eCourts portals | per case, per hearing | **Not used.** Protected by CAPTCHA, and bulk download isn't permitted. |

See [docs/data_acquisition.md](docs/data_acquisition.md) for download steps, licences and access limits.

**Reference run** (real data): 94,972 Delhi district-court cases filed in 2010 (DDL `cases_clean_2010`). 94,389 were scored against peer groups. 3,739 were flagged, and 47 of those flags sit on records with date inconsistencies. Run details are in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Quick start

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

1. Download real data (CC0 on Dataverse; about 390 MB for 2010). The commands are in [docs/data_acquisition.md](docs/data_acquisition.md).
2. Extract a scope. This example uses Delhi (state code 26). Party/advocate names and CNR numbers are never read.

```bash
python -m tareekh_radar.cli ddl-extract --dta data/raw/ddl/cases_clean_2010.dta --states 26 --out data/raw/ddl/delhi_2010 --name ddl_2010_delhi
```

3. Validate, clean, featurise and score:

```bash
python -m tareekh_radar.cli process --cases data/raw/ddl/delhi_2010/cases.parquet --mapping data/raw/ddl/delhi_2010/mapping.yaml
```

4. Run the research evaluation (method comparison, group comparison, missing-data sensitivity):

```bash
python -m tareekh_radar.cli evaluate --dataset ddl_2010_delhi
```

5. Launch the app and the API:

```bash
streamlit run app/streamlit_app.py
```

```bash
uvicorn tareekh_radar.api:app --reload
```

6. Run the tests:

```bash
python -m pytest
```

### Human validation (no labels are invented)

```bash
python -m tareekh_radar.cli review-export --dataset ddl_2010_delhi
```

Fill in `reviewer_verdict` (`pattern_confirmed`, `legitimate_explanation`, `data_artifact`, `not_unusual`) in `data/annotations/ddl_2010_delhi_anomaly_review.csv`. The sheet is blind: scores and flags are hidden, and it includes random unflagged controls. Then run:

```bash
python -m tareekh_radar.cli evaluate --dataset ddl_2010_delhi --review-file data/annotations/ddl_2010_delhi_anomaly_review.csv
```

### Hearing-level sources (e.g. DAKSH)

```bash
python -m tareekh_radar.cli process --cases cases.csv --hearings hearings.csv --mapping config/mappings/daksh_template.yaml
```

```bash
python -m tareekh_radar.cli annotate-export --dataset <name> --n 300
```

```bash
python -m tareekh_radar.cli train-classifier --labels data/annotations/<name>_to_annotate.csv
```

## Application modules

- **Court Overview**: dataset provenance, geographic scope, snapshot date and licence on every page. Also case and hearing totals, flags by severity, and per-court tables.
- **Case Timeline**: search by pseudonymised case id to see the chronological record, with gaps, invalid dates (shown with their raw values), the explanation and the source record pointer.
- **Anomaly Radar**: ranked flags with filters for court, case type, stage, severity and completeness. Flags on records with data-quality problems are hidden by default. Every flag carries a full explanation.
- **Data Quality Monitor**: missingness, invalid and out-of-range dates, chronology violations, duplicates, ineligible cases and classification uncertainty. These are kept separate from the findings.
- **Research Evaluation**: score distributions, statistical vs Isolation Forest vs raw baselines, top-k overlap, court concentration, sensitivity to missing records, human validation results and group comparisons.

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | modules, data flow, storage |
| [docs/data_acquisition.md](docs/data_acquisition.md) | sources, download commands, licences, access limits |
| [docs/data_dictionary.md](docs/data_dictionary.md) | contracts for cases, hearings, features, anomaly results |
| [docs/configuration.md](docs/configuration.md) | every config section |
| [docs/methodology.md](docs/methodology.md) | cleaning, classification, features, anomaly model, explanations |
| [docs/evaluation.md](docs/evaluation.md) | evaluation design, leakage controls, research questions |
| [docs/limitations.md](docs/limitations.md) | known limitations and assumptions |
| [docs/provenance.md](docs/provenance.md) | provenance, pseudonymisation, privacy |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | done, pending, known issues, decisions |

## Citation of data

If you use DDL data, cite: Ash, Asher, Bhowmick, Bhupatiraju, Chen, Devi, Goessmann, Novosad, Siddiqi, *In-Group Bias in the Indian Judiciary: Evidence from 5 Million Criminal Cases*, The Review of Economics and Statistics (2025), doi:10.1162/rest_a_01569. DDL's site states CC BY-NC-SA 4.0 for its public judicial data, so use it non-commercially.

Code licence: MIT (see [LICENSE](LICENSE)).
