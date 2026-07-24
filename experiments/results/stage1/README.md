# Stage 1 results

`stage1_results.csv` is the authoritative row-level table for all six datasets.
`runs.csv` provides one row per source run, including row counts, terminal
counts, aggregate training time, resource peaks, provenance and the path inside
the evidence archive. `evidence_contents.csv` lists the size and SHA-256 digest
of every archived file. `source_inventory.csv` records the remote URI, local
copy and checksum for each authoritative source ledger; the copies live under
`runs/<outer_run_id>/source_results.csv`.

The external archive is `stage-1-metadata-20260724.tar.zst` in the project
Google Drive results `stage-1` folder. It contains the small operational files
needed for audit and diagnosis:

- result, metric and resource CSVs;
- run status, timing, identity and training-status JSON;
- launcher and scientific logs; and
- terminal exit markers.

PLYs, databases, reconstructed models, rendered images and large per-image
manifests are excluded. Full scientific artefacts remain at the immutable
object-storage prefixes recorded in `source_uri`.

Extract with:

```bash
tar --zstd -xf stage-1-metadata-20260724.tar.zst
```
