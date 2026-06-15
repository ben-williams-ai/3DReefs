# Research: Splat Cleanup And SOG Compression

## Decision: Use Explicit Post-Processing Steps

Use `splat.cleanup`, `splat.merge`, `splat.sog`, and `splat.postprocess` for this feature.

**Rationale**: Feature 3 already uses splat-related steps for outlier filtering, patching, and training. Explicit post-processing steps avoid surprising users and make resume/overwrite checks precise.

**Alternatives considered**:

- Redefine `splat` to include cleanup, merge, and SOG. Rejected because it changes the meaning of an existing Feature 3 workflow.
- Only expose individual cleanup and SOG steps. Rejected because the main desired output is the full cleaned merged site splat and final SOG sequence.

## Decision: Prefer Completed Patch Splats, Then Highest Iteration

For each patch, select `splat_finished.ply` when present. If it is absent, use the highest-iteration usable patch PLY and classify the source as warning or severe warning based on completion ratio.

**Rationale**: This matches the current Feature 3 training naming convention and the user requirement that incomplete patch outputs may be used but must be recorded clearly.

**Alternatives considered**:

- Fail whenever `splat_finished.ply` is missing. Rejected because the requested behaviour allows incomplete outputs with warnings.
- Always use the numerically highest `splat_*.ply`, even when `splat_finished.ply` exists. Rejected because completed training should be the preferred source.

## Decision: Use Wildflow For Cleanup

Implement cleanup with `wildflow.splat.cleanup_splats` and the evidenced old coral defaults: `max_area: 0.004`, `min_neighbors: 20`, `radius: 0.05`, `filter_boundaries: true`, and `boundary_buffer: 0.1`.

**Rationale**: The old process used `wildflow.splat.cleanup_splats` and worked well for coral patch cleanup. Wildflow is available as a public Python package, and using it avoids weaker fallback cleanup that does not implement neighbour and area filtering.

**Alternatives considered**:

- Copy the old cleanup script directly. Rejected because the old repo was intentionally bloated and this feature should integrate cleanly with the new run-record/config system.
- Keep `splat-transform` cleanup as a fallback. Rejected because it does not cover the evidenced neighbour/area cleanup semantics and would add maintenance overhead.
- Skip cleanup and merge raw patch splats. Rejected by the feature spec.

## Decision: Use Wildflow For PLY Merge And `splat-transform` For Final SOG

Use `wildflow.splat.merge_ply_files` for merging cleaned PLY inputs into one site-level cleaned PLY. Use the configured `splat-transform` CLI for converting that merged PLY into one final SOG.

**Rationale**: The old PLY merge path used wildflow and should stay consistent with the cleanup toolchain. `splat-transform v1.10.2` remains the appropriate tool for final SOG export.

**Alternatives considered**:

- Use `splat-transform` for cleaned PLY merge. Rejected because Feature 5 now standardises on wildflow for cleanup and PLY merge.
- Implement a custom binary PLY merge immediately. Rejected because wildflow already supports this use case.

## Decision: One Concise Post-Processing Manifest

Write one post-processing manifest with cleanup, merge, SOG, warnings, decisions, and output sections. Stream external command output to existing logs and update central run status/timings after each stage.

**Rationale**: The project has already simplified redundant reporting. One manifest avoids mismatches between duplicate markdown reports, JSON files, and logs while still preserving per-patch status.

**Alternatives considered**:

- Write separate cleanup, merge, and SOG reports. Rejected because it repeats information and makes later runs harder to audit.
- Only rely on terminal logs. Rejected because resume and later analysis need structured stage records.

## Decision: Up-Front Existing Output Resolution

Detect existing cleaned patch outputs, merged PLY, and final SOG during preflight. Apply `resume`, `overwrite`, or `fail` decisions before any requested post-processing command runs.

**Rationale**: This follows the project constitution and prevents unattended long runs from pausing mid-run.

**Alternatives considered**:

- Prompt per patch as conflicts are encountered. Rejected because mid-run prompts are not acceptable for long jobs.
- Always overwrite generated post-processing outputs. Rejected because users may be comparing settings and need explicit intent before destructive work.

## Decision: Partial Status For Failed Requested SOG After Valid Merge

If SOG export is requested and fails after a valid merge, preserve the merged PLY, mark the post-processing run as partial, and emit prominent warnings so the user can rerun only `splat.sog`.

**Rationale**: The merged PLY is useful and should not be discarded or hidden behind a generic failure state. The structured manifest records that final SOG failed, while the run remains resumable from `splat.sog`.

**Alternatives considered**:

- Treat the whole command as fully complete because the merged PLY exists. Rejected because the requested final SOG artefact failed and must remain visible in warnings and manifests.
- Delete the merged PLY on SOG failure. Rejected because the merged PLY remains a valid useful output.
