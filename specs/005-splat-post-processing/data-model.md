# Data Model: Splat Cleanup And SOG Compression

## PatchTrainingSource

Represents the trained patch PLY selected as input to cleanup.

**Fields**:

- `patch_id`: Stable patch identifier, for example `p000`.
- `source_file`: Path to the selected PLY relative to the run directory.
- `source_kind`: `finished` or `iteration`.
- `requested_iterations`: Configured patch training iteration target when known.
- `completed_iterations`: Completed iteration count when known.
- `completion_ratio`: `completed_iterations / requested_iterations` when both are known.
- `severity`: `normal`, `warning`, `severe_warning`, or `failed`.
- `usable`: Whether the source may be cleaned.
- `reason`: Human-readable reason for selection or exclusion.

**Validation rules**:

- Prefer `splat_finished.ply` when present.
- Otherwise select the highest-iteration usable `splat_<iterations>.ply`.
- Mark incomplete sources below 80 percent of requested iterations as `severe_warning`.
- Mark incomplete sources from 80 percent up to but below complete as `warning`.

## CleanupStatus

Represents the cleanup result for one patch.

**Fields**:

- `patch_id`
- `source`: `PatchTrainingSource`
- `output_file`: Cleaned PLY path relative to the run directory, when produced.
- `status`: `pending`, `complete`, `failed`, `skipped`, or `reused`.
- `cleanup_settings`: Effective cleanup settings used for this patch.
- `before_splat_count`: Source PLY vertex count when available.
- `after_splat_count`: Cleaned PLY vertex count when available.
- `duration_seconds`: Cleanup duration when run.
- `warnings`: List of concise warning codes/messages.

**Validation rules**:

- Cleanup must not overwrite an existing cleaned output unless an up-front overwrite decision exists.
- Cleanup settings must use scene-relative terminology in user-facing summaries.
- A large before/after reduction is recorded but is not a special warning by default.

## MergeInputRecord

Represents the per-patch inclusion decision for the site-level merge.

**Fields**:

- `patch_id`
- `cleaned_file`: Cleaned PLY path relative to the run directory, when available.
- `included`: Whether this patch is included in the merge.
- `excluded_reason`: Reason when excluded.
- `source_severity`: Severity inherited from the selected training source.
- `incomplete_source`: Whether the cleaned source came from incomplete training.

**Validation rules**:

- Raw uncleaned splats must not be used when cleaned outputs are expected.
- Missing or failed cleaned outputs are excluded by default but recorded prominently.

## MergeStatus

Represents the merged cleaned site-level PLY.

**Fields**:

- `status`: `pending`, `complete`, `failed`, `skipped`, `reused`, or `partial`.
- `output_file`: Merged cleaned PLY path relative to the run directory.
- `inputs`: List of `MergeInputRecord`.
- `included_count`: Number of cleaned patches included.
- `excluded_count`: Number of patches excluded.
- `severe_warning_count`: Number of included patches derived from severe incomplete sources.
- `duration_seconds`: Merge duration when run.
- `warnings`: List of concise warning codes/messages.

**Validation rules**:

- At least one cleaned input is required for merge.
- Existing merged output must be resolved by an up-front reuse, overwrite, or fail decision.

## SogStatus

Represents final SOG export from the merged cleaned site splat.

**Fields**:

- `status`: `pending`, `complete`, `failed`, `skipped`, or `reused`.
- `source_merged_ply`: Merged cleaned PLY path relative to the run directory.
- `output_sog`: Final SOG path relative to the run directory.
- `tool_version`: Observed `splat-transform` version.
- `command_summary`: Redacted command summary without private absolute paths.
- `duration_seconds`: Export duration when run.
- `failure_reason`: Concise failure reason when failed.

**Validation rules**:

- SOG export requires a valid merged cleaned PLY.
- If requested SOG export fails, post-processing is partial even when the merged PLY is valid.

## PostProcessingManifest

Run-level manifest for cleanup, merge, and SOG.

**Fields**:

- `run_id`
- `requested_steps`
- `started_at`, `updated_at`, `completed_at`
- `decisions`: Reuse/overwrite/fail decisions gathered before work.
- `cleanup`: List of `CleanupStatus`.
- `merge`: `MergeStatus`
- `sog`: `SogStatus`
- `warnings`: Deduplicated warning summary.
- `effective_settings`: Post-processing settings relevant to source selection, cleanup, merge, and SOG.

**State transitions**:

- `not_started` -> `running` -> `complete`
- `not_started` -> `running` -> `partial`
- `not_started` -> `failed`
- `running` -> `interrupted`

**Validation rules**:

- Manifest must be written before the first requested post-processing operation starts.
- Manifest must update after each cleanup patch, merge, and SOG stage.
- Final summary must prominently show missing patches, severe incomplete sources, and SOG failure when present.
