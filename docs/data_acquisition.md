# Data acquisition

Tareekh Radar ships with no data. Every dataset must be obtained by the researcher from a legally accessible source. The project never scrapes CAPTCHA-protected portals and never bypasses access controls.

## 1. Development Data Lab (DDL) eCourts case data, 2010–2018 (supported)

- **What:** about 80 million district- and sessions-court case records collected from eCourts and de-identified by DDL. The replication release used here has one file per filing year (`cases_clean_2010` … `cases_clean_2018`).
- **Where:** Harvard Dataverse, `doi:10.7910/DVN/GHLGSW` (published 2024-12-20). This is the replication package for Ash et al., REStat 2025. DDL's public page is <https://www.devdatalab.org/judicial-data>.
- **Licence:** the Dataverse record shows **CC0 1.0**. DDL's own page states **CC BY-NC-SA 4.0** for its public judicial data. Use the data non-commercially and cite the paper to satisfy both.
- **Granularity:** **one row per case.** Fields used: `ddl_case_id, year, state, state_name, district, district_name, court, court_name, date_of_filing, date_of_decision, date_first_list, date_last_list, date_next_list, purpose_name, type_name, disp_name, criminal`. `purpose_name`, `type_name` and `disp_name` are numeric codes, decoded per year with the key files.
- **Not available:** a per-hearing history. Adjournment counts, non-progress streaks and stage loops therefore **cannot** be computed from DDL and are reported as unavailable.
- **Sensitive columns (never read):** `pet_name, def_name, pet_adv, def_adv, cino, case_no`, the inferred religion/gender columns, judge identifiers and designations.

### Download (public; no login)

These commands use the Dataverse access API. File ids are from the dataset version listed on 2026-11-13. List them again with the first command if they change.

```bash
curl -s "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/GHLGSW" -o dv.json
```

```bash
mkdir -p data/raw/ddl && cd data/raw/ddl
for id_name in 10794661:purpose_name_key.tab 10794659:type_name_key.tab 10794671:disp_name_key.tab 10794674:cases_state_key.tab 10794672:cases_district_key.tab 10794667:cases_clean_2010.zip; do curl -sSL -o "${id_name#*:}" "https://dataverse.harvard.edu/api/access/datafile/${id_name%%:*}?format=original"; done
unzip cases_clean_2010.zip
```

File sizes at download time: `cases_clean_2010.zip` 385.7 MB (3.5 GB unzipped, 4,281,327 rows), `cases_clean_2011.zip` 883 MB, key files under 10 MB each. The `.tab` keys are Stata files despite their extension.

### Convert to the data contract

```bash
python -m tareekh_radar.cli ddl-extract --dta data/raw/ddl/cases_clean_2010.dta --states 26 --out data/raw/ddl/delhi_2010 --name ddl_2010_delhi
```

`--states` takes eCourts state codes such as `01` Maharashtra, `13` Uttar Pradesh or `26` Delhi. `--districts` takes `SS-DD` codes. Leaving both out extracts every state (4.28M rows for 2010; about 6 minutes). The adapter writes `cases.parquet` and a `mapping.yaml` that records the source, licence, scope and row counts.

## 2. DAKSH High Court data (hearing level; access on request)

- DAKSH publishes case-level and **hearing-level** data from six High Courts (2015 onwards; about 5.86 lakh cases and 32 lakh hearings), plus a data dictionary at <https://www.dakshindia.org/data-dictionary/>.
- Access is through a form or login (<https://database.dakshindia.org/>). Open Justice India reported the form as not working and suggests emailing `info@dakshindia.org`. Licence reported as CC BY-NC 4.0, but **confirm the licence in writing** because DAKSH pages differ.
- Once you have the files, map their columns with a mapping YAML (template: `config/mappings/daksh_template.yaml`). Then run `process --cases … --hearings …`. The hearing-level pipeline covers event classification, adjournment features and hearing timelines.

## 3. NJDG / eCourts services (not used)

The NJDG dashboards publish aggregate statistics only. Case-status pages on eCourts are protected by CAPTCHA. Being visible to the public does not grant permission to bulk-download, so this project does not collect data from these portals. Institutional API access is granted by the eCourts project on request.

## Recording provenance

Every processed dataset stores `manifest.json` with the source, licence, scope, file SHA-256 hashes, row counts and dropped columns. It also stores `run_info.json` with the config hash, versions and reference date. Each case keeps a `source_reference` pointer (for DDL: DOI, file and pseudonymised case id).
