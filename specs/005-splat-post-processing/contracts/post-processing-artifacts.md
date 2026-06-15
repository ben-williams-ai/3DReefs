# Artifact Contract: Splat Cleanup And SOG Compression

All paths are relative to `project.dir/runs/<run_id>/`.

## Inputs

Feature 5 reads Feature 3 outputs:

```text
splat/patches/<patch_id>/
```

Each patch may contain:

- `splat_finished.ply`: preferred completed training output.
- `splat_<iterations>.ply`: incomplete or checkpoint output.
- Feature 3 patch/training metadata used to determine requested and completed iterations.

Feature 5 must not modify training outputs in place.

Boundary cleanup reads Feature 3 patch bounds from the canonical nested
`patch_metadata.json["bounds"]` object. Old top-level boundary keys are not a
valid input format for this codebase.

## Cleanup Outputs

Cleaned patch PLYs are written beside the selected patch source or in the patch post-processing area using a deterministic cleaned suffix:

```text
splat/patches/<patch_id>/splat_finished_clean.ply
splat/patches/<patch_id>/splat_<iterations>_clean.ply
```

Implementation may store these under a patch-local post-processing subdirectory if that is already the local convention, but the post-processing manifest must record the exact relative path.

## Merge Outputs

One primary cleaned site-level PLY is written:

```text
splat/merged/merged_splat.ply
```

The merge must use cleaned patch PLYs only when `require_cleaned` is true.

## SOG Outputs

One final SOG is written from the merged cleaned PLY:

```text
splat/merged/merged_splat.sog
```

Per-patch SOG outputs are not part of the default main pipeline for this feature.

## Structured Records

Feature 5 writes one concise post-processing manifest:

```text
splat/postprocess/postprocess_manifest.json
```

The manifest records:

- selected patch source for every patch considered
- cleanup status for every patch considered
- merge included/excluded records
- merged PLY output status
- final SOG output status
- warnings and severity
- timings and reuse/overwrite decisions

The normal Feature 1 run records must also be updated:

```text
run_manifest.json
run_status.json
timings.json
logs/pipeline.log
logs/warnings.log
logs/splat_transform.log
```

`logs/splat_transform.log` stores final SOG command output. Wildflow cleanup and merge status should be represented in the post-processing manifest and existing pipeline logs without adding duplicate reports.
