# Tareekh Radar

Tareekh Radar is a research tool. It finds **statistically unusual case-progression patterns** in Indian court records, such as very long pendency, long periods without a listing, long delays to first listing, and (where per-hearing data exists) repeated adjournments, non-progress streaks and stage loops. It explains every flag in plain language.

> **What it is not.** The tool reports statistical deviations from comparable cases in the same dataset. An unusual pattern can have legitimate procedural explanations, and it can also be a data error. **Nothing in this project establishes misconduct or responsibility by any judge, lawyer, litigant or court official.**

## Data: real sources only

The project ships **no data** and **no generated or synthetic records**. All analysis runs on public judicial data that you download yourself.

| Source | Granularity | Status in this project |
|---|---|---|
| **Development Data Lab (DDL) eCourts case data 2010–2018**, Harvard Dataverse `doi:10.7910/DVN/GHLGSW` | one row per case: filing, decision, first/last/next listing dates, purpose, type, disposal | **Supported** (`ddl-extract` adapter). Used for the reference analysis. |
| DAKSH High Court data (case + hearing level) | per hearing | Generic hearing-level pipeline ready. Access is through DAKSH's form or email, which the user must request. |
| NJDG / eCourts portals | per case, per hearing | **Not used.** Protected by CAPTCHA, and bulk download isn't permitted. |

See [docs/data_acquisition.md](docs/data_acquisition.md) for download steps, licences and access limits.

**Reference run** (real data): 94,972 Delhi district-court cases filed in 2010 (DDL `cases_clean_2010`). 94,389 were scored against peer groups. 3,727 were flagged, and 48 of those flags sit on records with date inconsistencies. Run details are in [PROJECT_STATUS.md](PROJECT_STATUS.md).

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
