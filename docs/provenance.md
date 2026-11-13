# Data provenance and privacy

## Provenance chain

1. **Source file**: path and SHA-256 recorded in `manifest.json` (`files`).
2. **Source licence, scope, access notes**: `mapping.yaml` → `manifest.json`.
3. **Each case**: `source_reference`. For DDL this is `ddl:doi:10.7910/DVN/GHLGSW/<file>#ddl_case_id=<pseudonym>`. Raw date strings are kept in `*_raw` columns next to the parsed values and their status.
4. **Each hearing** (hearing-level sources): `source_reference`, `source_row`, and the classification decision log.
5. **Each flag**: explanation JSON listing the supporting hearing ids or record fields, the peer definition and the config used.
6. **Each run**: `run_info.json` (UTC timestamp, package and Python versions, config hash, reference date, classification mode, whether ML or human labels were applied) and `config.json`. Evaluation runs are stored under `runs/<timestamp>_<config hash>_<label>/` with a config snapshot.

## Pseudonymisation

- `case_id` → `C-` + the first 10 hex characters of HMAC-SHA256(salt, case_id). Hearing ids derived from a case id are re-keyed consistently.
- The salt comes from the env var `TAREEKH_SALT`, or `data/.salt` (auto-created and gitignored).
- `id_map.LOCAL_ONLY.parquet` allows an authorised researcher to trace a result back to the source. Do not distribute it.

## Columns never ingested

- **DDL:** party names, advocate names, CNR (`cino`), case numbers, inferred religion/gender, judge identifiers and designations.
- **Other sources:** any column not in the data contract is dropped on load (`privacy.drop_unmapped_columns`). Dropped column names are recorded in the manifest.

## What is committed

Only code, configuration, tests and documentation. `data/`, `models/` and `runs/` are gitignored.
