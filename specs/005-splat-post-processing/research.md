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

## Decision: Preserve Old Coral Cleanup Semantics Behind An Adapter

Implement cleanup through a backend adapter that preserves the evidenced old coral defaults: `max_area: 0.004`, `min_neighbors: 20`, `radius: 0.05`, `filter_boundaries: true`, and `boundary_buffer: 0.1`.

**Rationale**: The old process used `wildflow.splat.cleanup_splats` and worked well for coral patch cleanup. The new pipeline should keep that behaviour but isolate it behind a clean interface. The current `uv` environment does not expose `wildflow`, so implementation must either add and validate the correct cleanup backend or provide an equivalent tested implementation before real cleanup can run.

**Alternatives considered**:

- Copy the old cleanup script directly. Rejected because the old repo was intentionally bloated and this feature should integrate cleanly with the new run-record/config system.
- Use only `splat-transform` filters for cleanup. Rejected because they do not cover the evidenced neighbour/area cleanup semantics.
- Skip cleanup and merge raw patch splats. Rejected by the feature spec.

## Decision: Use `splat-transform` For Merge And Final SOG

Use the configured `splat-transform` CLI for merging cleaned PLY inputs into one site-level cleaned PLY and for converting that merged PLY into one final SOG.

**Rationale**: `splat-transform v1.10.2` is already part of the toolchain and supports multiple input files with PLY and SOG outputs. This keeps merge and compression in one validated external tool rather than reintroducing old merge dependencies.

**Alternatives considered**:

- Use the old `wildflow.splat.merge_ply_files` path. Rejected because the dependency is not available in the current environment and `splat-transform` covers the required merge/export interface.
- Implement a custom binary PLY merge immediately. Rejected because the external tool already supports this use case and custom PLY handling would increase risk.

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

## Decision: Non-Zero Exit For Failed Requested SOG

If SOG export is requested and fails after a valid merge, preserve the merged PLY and mark the post-processing run as partial, but return a failed command status.

**Rationale**: The merged PLY is useful and should not be discarded, but the requested workflow did not fully complete. A non-zero exit prevents automation from mistaking a missing final SOG for success.

**Alternatives considered**:

- Return success because the merged PLY exists. Rejected because the requested final artefact failed.
- Delete the merged PLY on SOG failure. Rejected because the merged PLY remains a valid useful output.
