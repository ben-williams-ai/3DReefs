# Stage 2 results

`stage2_results.csv` is the success-only table used by downstream analysis.
`stage2_all_results.csv` is the complete audit table, and
`stage2_failures.csv` contains its terminal failure rows. `runs.csv` indexes the
complete audit table with one row per outer run, including row counts, terminal
counts, aggregate training time, resource peaks, provenance and the path inside
the evidence archive.

`source_inventory.csv` records the remote URI, local copy and checksum for each
authoritative source ledger; the copies live under
`runs/<outer_run_id>/results_splat.csv`. `evidence_contents.csv` lists the size
and SHA-256 digest of every archived evidence file.

Regenerate and validate the local tables with
`uv run python scripts/consolidate_stage2_results.py`.

The external archive is `stage-2-metadata-20260724.tar.zst` in the project
Google Drive results `stage-2` folder. It contains the small operational files
needed for audit and diagnosis:

- result, metric, loss-history and resource CSVs;
- run status, timing, identity, configuration and training-status JSON;
- launcher and scientific logs; and
- terminal exit markers.

PLYs, rendered images, evaluation image trees and large reconstruction/source
manifests are excluded. Full scientific artefacts remain at the immutable
object-storage prefixes recorded in `source_uri`.

Extract with:

```bash
tar --zstd -xf stage-2-metadata-20260724.tar.zst
```
