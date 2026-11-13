# Architecture

```
raw files (CSV / Excel / JSON / Parquet / DDL .dta)
   │  adapters/ddl.py           source-specific conversion (DDL eCourts)
   ▼
ingestion.py                    read as strings, map columns → contract, provenance manifest
   ▼
validation.py                   structural checks (fatal errors vs warnings)
   ▼
cleaning.py                     dates, duplicates, case types, stages, chronology flags, quality report
   ▼
privacy.py                      HMAC pseudonyms for case/hearing ids (salt never stored with outputs)
   ▼
classification.py               (hearing-level only) rules → optional TF-IDF/LogReg → human overrides
   ▼
features.py                     per-case features: hearing-level (loop) + case-level (vectorised)
   ▼
anomaly.py                      peer groups → robust z / percentiles → flags + explanations; Isolation Forest
   ▼
storage.py                      Parquet per table + DuckDB per dataset + JSON metadata
   ▼
service.py ──► api.py (FastAPI)          evaluation.py (research metrics, review, sensitivity)
          └──► app/streamlit_app.py      cli.py (all commands)
```

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | Loads `config/default.yaml` plus overrides. Validates (e.g. every peer level must contain a case type). Computes the config hash. |
| `schemas.py` | Data contracts: CASES, HEARINGS, ANALYSIS_RESULTS, event classes, quality flags. |
| `adapters/ddl.py` | Streams DDL `.dta` files in chunks, decodes codes with per-year keys, never reads name/CNR columns. |
| `ingestion.py` | File readers, column mapping, generated hearing ids, SHA-256 provenance. |
| `validation.py` | Contract checks. A cases-only dataset is valid and selects case-level mode. |
| `cleaning.py` | Explicit date formats (day-first first), out-of-range years, duplicate logs, orthographic case-type keys, stage regexes, chronology flags, status inference only from unambiguous evidence. |
| `classification.py` | Rule classifier (priority, negation, conflicts become UNKNOWN), ML baseline that abstains, decision log, human labels. |
| `features.py` | Hearing features (streaks, stage returns, intervals, days since substantive progress) and case-level features (duration, dormancy, time to first listing, next-listing gap). |
| `anomaly.py` | Hierarchical peer assignment, vectorised robust statistics, flags, severity, explanations, quality-issue marker, Isolation Forest. |
| `evaluation.py` | Classifier metrics and grouped hold-out, method comparison, blind human review, sensitivity, group comparison, run directories. |
| `service.py` | Read-side access used by the API and the app (cached per dataset file version). |
| `api.py` | `/health`, `/datasets`, `/datasets/{n}/overview|quality|anomalies`, `/datasets/{n}/cases/{id}[/timeline]`, `POST /classify`. |
| `app/streamlit_app.py` | Five modules: Overview, Timeline, Radar, Data Quality, Research Evaluation. |

## Analysis modes

The mode is chosen automatically from the data:

- **hearing**: per-hearing records exist. Classification, hearing features and the `anomaly.modes.hearing` config are used.
- **case**: one row per case (DDL). Case-level date features and the `anomaly.modes.case` config are used. Hearing metrics are null, with the reason recorded.

## Storage layout

```
data/processed/<dataset>/
  cases.parquet  hearings.parquet  features.parquet  anomalies.parquet
  rejected.parquet  duplicates.parquet  decision_log.parquet
  tareekh.duckdb                 same tables, SQL-queryable
  manifest.json  quality_report.json  run_info.json  config.json
  evaluation.json  sensitivity.csv  group_comparison.csv   (after `evaluate`)
  id_map.LOCAL_ONLY.parquet      re-identification key - never share
runs/<UTC timestamp>_<config hash>_<label>/   experiment outputs + config snapshot
```

`data/`, `models/` and `runs/` are gitignored. No data is committed.
