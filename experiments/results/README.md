# Experiment results

This directory is the lightweight, version-controlled interface for downstream
analysis. Large models, images, verbose logs and per-iteration diagnostics stay
in object storage or the matching Google Drive evidence archive.

Each stage contains:

- an authoritative row-level results CSV;
- `runs.csv`, the uniform run-level index;
- `source_inventory.csv` and `runs/`, immutable copies of source result ledgers;
- `evidence_contents.csv`, checksums for every archived evidence file;
- generated summary figures; and
- a README describing the schema and external evidence archive.

Downstream code should read the stage README, join row-level data to `runs.csv`
by `outer_run_id`, and treat `source_uri` as immutable provenance. Do not depend
on ignored `scratch/` directories.
