# Feature Specification: Splat Cleanup And SOG Compression

**Feature Branch**: `005-splat-post-processing`  
**Created**: 2026-06-15  
**Status**: Draft  
**Input**: User description: "Create Feature 4: Splat Cleanup And SOG Compression for 3DReefs. Take trained patch splats from Feature 3, clean them, merge cleaned patch PLYs into one primary site-level splat, then run SOG compression by default. Validate tooling up front, record concise manifests/logs/timings/warnings, and keep COLMAP, patch generation, LFS training, PlayCanvas, NanoGS, and LOD out of scope."

## Clarifications

### Session 2026-06-15

- Q: When cleaned outputs are missing, failed, or derived from severely incomplete training, what should the default merge behaviour be? → A: Warn and continue by default with available cleaned patches, while prominently flagging missing or severe patches.
- Q: When cleanup removes a large proportion of splats from a patch, what should the default behaviour be? → A: Do not special-case removal proportion; record before/after splat counts only.
- Q: If final SOG export fails after a valid merged cleaned site splat was created, what should the default overall status be? → A: Mark post-processing partial: merged cleaned PLY is valid, final SOG failed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clean Trained Patch Splats (Priority: P1)

A reef reconstruction researcher can take completed patch training outputs and produce cleaned patch splats that are ready for site-level merging, while preserving a clear record of which training output was used for each patch.

**Why this priority**: Cleaning is the first post-training quality-control step. If patch outputs are not cleaned consistently, the final merged reef splat will inherit noisy, oversized, or boundary-overlap artefacts.

**Independent Test**: Can be tested on a completed Feature 3 run by requesting cleanup only and confirming that every eligible patch receives a cleaned output or an explicit skipped/failed status, with concise records showing the source file, completion state, cleanup outcome, warnings, and timing.

**Acceptance Scenarios**:

1. **Given** a completed patch training run with `splat_finished.ply` for every patch, **When** the researcher runs cleanup, **Then** the system creates cleaned patch outputs for all eligible patches and records the source and result for each patch.
2. **Given** a patch has no `splat_finished.ply` but has an incomplete iteration output, **When** cleanup runs, **Then** the system uses the highest-iteration usable output, records that choice, and applies the configured warning severity.
3. **Given** cleanup thresholds are shown to the researcher, **When** the run summary is presented, **Then** the thresholds are described as scene-relative values rather than metres or any other absolute unit.

---

### User Story 2 - Merge Cleaned Patches Into One Site Splat (Priority: P1)

A researcher can combine the cleaned patch splats into one primary cleaned site-level splat that represents the whole reconstructed reef area.

**Why this priority**: The desired final deliverable is a single cleaned site splat, not a loose collection of patch files. Merging must happen before the default final SOG export.

**Independent Test**: Can be tested after cleanup by requesting merge/post-processing and confirming that the run produces one merged cleaned site splat, plus a manifest listing every patch source used or excluded.

**Acceptance Scenarios**:

1. **Given** all trained patches have cleaned outputs, **When** merging runs, **Then** the system creates one merged cleaned site-level splat and records every cleaned patch source used.
2. **Given** some patches are missing cleaned outputs, **When** merging is requested, **Then** the system reports the missing patches before merge work starts and continues by default with available cleaned patches unless the researcher requests stricter behaviour.
3. **Given** a patch only has a cleaned output derived from incomplete training, **When** the patch is included in the merge, **Then** the final merge report prominently records the incomplete source and warning severity.

---

### User Story 3 - Export Final Site SOG (Priority: P2)

A researcher can convert the merged cleaned site-level splat into a final SOG output for downstream viewing or delivery.

**Why this priority**: SOG is the compact export format for the final post-processed reef splat, but it depends on the cleaned merged site splat being available first.

**Independent Test**: Can be tested from an existing merged cleaned site splat by requesting SOG export only and confirming that one final SOG output, timing record, warning summary, and source reference are written.

**Acceptance Scenarios**:

1. **Given** a merged cleaned site splat exists and SOG output is enabled, **When** SOG export runs, **Then** the system creates one final SOG output linked to that merged source.
2. **Given** SOG export is requested but the required conversion tool is unavailable or unsupported, **When** preflight runs, **Then** the system fails before cleanup, merge, or compression work starts.
3. **Given** SOG export is requested without an existing merged cleaned site splat, **When** merge is not part of the requested steps and no valid merged source exists, **Then** the system fails clearly before compression work starts.

---

### User Story 4 - Resume Or Overwrite Post-Processing Safely (Priority: P2)

A researcher can rerun cleanup, merge, or SOG export without accidental overwrites or mid-run prompts.

**Why this priority**: Cleanup, merging, and export may be run repeatedly while tuning settings. Decisions about reusing, overwriting, or stopping must be made up front so long unattended jobs do not pause part-way through.

**Independent Test**: Can be tested by creating existing cleaned, merged, and SOG outputs, then rerunning requested post-processing stages with resume, overwrite, and fail policies and confirming all decisions are resolved before any requested work starts.

**Acceptance Scenarios**:

1. **Given** existing cleaned patch outputs are present, **When** cleanup is requested again, **Then** the system resolves whether to reuse, overwrite, or stop before cleaning any patch.
2. **Given** an existing merged site splat or final SOG is present, **When** merge or SOG export is requested again, **Then** the system resolves reuse or overwrite before starting any post-processing work.
3. **Given** relevant config values changed since a previous partial post-processing run, **When** the researcher resumes, **Then** the system warns about the changed values before continuing.

### Edge Cases

- Splat cleanup is requested before any Feature 3 patch training outputs exist.
- A patch directory exists but contains no usable PLY output.
- A patch has both `splat_finished.ply` and iteration-stamped outputs; the completed output should be preferred.
- A patch only reached less than 80 percent of requested iterations.
- A patch reached at least 80 percent but less than 100 percent of requested iterations.
- Cleanup produces no output.
- Cleanup removes a large proportion of splats; this is recorded through before/after counts but is not a special warning or failure by default.
- Cleaned patch outputs exist for only a subset of patches.
- Merge is requested when one or more cleaned patch outputs are missing.
- SOG export is requested when the merged cleaned site splat is missing.
- Existing cleaned, merged, or SOG outputs conflict with the requested run.
- The configured cleanup backend is missing, unsupported, or cannot create cleaned outputs.
- The configured post-processing conversion tool is missing, reports an unsupported version, or cannot create the requested merge or SOG output.
- Final SOG export fails after cleanup and merge have already produced a valid merged cleaned site splat.
- A non-interactive run requires a resume/overwrite decision that was not provided.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST take trained patch splats from a completed Feature 3 run as the input to post-processing.
- **FR-002**: The system MUST support running cleanup, merge, final SOG export, or the full post-processing sequence as requested pipeline steps.
- **FR-003**: The default full post-processing sequence MUST clean trained patch splats, merge cleaned patch PLYs into one site-level cleaned splat, and then create one final SOG from that merged site splat.
- **FR-004**: The system MUST prefer `splat_finished.ply` as the source for a patch when it exists.
- **FR-005**: When `splat_finished.ply` is absent, the system MUST select the highest-iteration usable patch PLY and record that selection.
- **FR-006**: The system MUST classify incomplete patch sources below 80 percent of requested iterations as severe warnings.
- **FR-007**: The system MUST classify incomplete patch sources at or above 80 percent but below complete as warnings.
- **FR-008**: The system MUST record normal status for completed patch sources.
- **FR-009**: The system MUST use the evidenced coral cleanup defaults unless the researcher overrides them.
- **FR-010**: The system MUST describe cleanup radius and boundary settings as scene-relative values, not metres or absolute-world units.
- **FR-011**: The system MUST produce a per-patch cleanup status showing the selected source, cleanup result, warning severity, and timing.
- **FR-012**: The system MUST record before/after splat counts for each cleanup output when those counts can be determined.
- **FR-013**: The system MUST NOT treat a large cleanup removal proportion as a special warning or failure by default.
- **FR-014**: The system MUST write concise post-processing manifests, warnings, timings, and command/output summaries through the existing run-record system without duplicating the same information across redundant reports.
- **FR-015**: The system MUST merge cleaned patch PLYs into one primary cleaned site-level PLY before default SOG export.
- **FR-016**: The system MUST NOT silently merge raw patch splats when cleaned patch outputs are expected.
- **FR-017**: The merge report MUST list every patch, whether it was included or excluded, the source file used, and any incomplete-training warning attached to that source.
- **FR-018**: If any severe incomplete patch source is included in the merge, the terminal summary, warnings log, and top-level post-processing manifest warning summary MUST show this prominently.
- **FR-019**: When cleaned outputs are missing or failed, the system MUST continue merging available cleaned patches by default, while prominently flagging excluded patches before merge and in the terminal summary, warnings log, and top-level post-processing manifest warning summary.
- **FR-020**: The system MUST create one final SOG from the merged cleaned site-level splat when SOG output is enabled.
- **FR-021**: The system MUST validate every configured post-processing backend or external tool needed by the requested workflow before any requested cleanup, merge, or SOG work starts.
- **FR-022**: The system MUST fail during preflight if cleanup, merge, or SOG output is requested and a required backend or external tool is missing, unsupported, or otherwise unusable.
- **FR-023**: If final SOG export fails after a valid merged cleaned site splat was created, the system MUST mark post-processing as partial, preserve the merged cleaned PLY as valid, and mark final SOG as failed.
- **FR-024**: The system MUST detect existing cleanup, merge, and SOG outputs before running any requested post-processing stage.
- **FR-025**: The system MUST resolve resume, reuse, overwrite, or stop decisions up front before any requested post-processing stage begins.
- **FR-026**: The system MUST warn up front when relevant cleanup, merge, SOG, or source-selection settings differ from a previous partial post-processing run.
- **FR-027**: Non-interactive runs MUST fail before post-processing work starts if a required reuse or overwrite decision has not been provided.
- **FR-028**: The system MUST allow a researcher to run SOG export only when a valid merged cleaned site-level splat already exists or has been explicitly selected by the requested workflow.
- **FR-029**: The system MUST keep COLMAP SfM, patch generation, LFS training, PlayCanvas packaging, NanoGS, and LOD out of this feature.
- **FR-030**: Public configs, examples, specs, and docs for this feature MUST NOT contain private local paths.
- **FR-031**: The system MUST validate the cleanup backend before cleanup or full post-processing starts and MUST NOT silently fall back to a different cleanup method.

### Key Entities *(include if feature involves data)*

- **Patch Training Source**: The trained patch PLY chosen for cleanup, including whether it is complete or incomplete and its completion severity.
- **Cleaned Patch Splat**: A cleaned PLY output for one trained patch, with the cleanup settings, source file, status, warnings, and timing that produced it.
- **Merge Input Record**: The per-patch decision used for site-level merge, including included/excluded status, cleaned source path, and any warning severity.
- **Merged Site Splat**: The primary cleaned site-level PLY created from cleaned patch outputs.
- **Final SOG Output**: The compressed SOG representation created from the merged cleaned site splat.
- **Post-Processing Manifest**: The run-level record tying together cleanup statuses, merge inputs, final outputs, timings, warnings, and resume/overwrite decisions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a completed Feature 3 test run, cleanup-only execution classifies 100 percent of patch training sources as complete, warning, severe warning, failed, or skipped before reporting completion.
- **SC-002**: Merge execution produces exactly one primary cleaned site-level splat from available cleaned patches and a merge summary listing 100 percent of patches as included or excluded.
- **SC-003**: On a run with a valid merged cleaned site splat and SOG enabled, SOG export produces exactly one final SOG output and records the merged source used.
- **SC-004**: In tested resume, overwrite, and fail-policy scenarios, 100 percent of required post-processing decisions are resolved before the first cleanup, merge, or SOG operation starts.
- **SC-005**: When incomplete patch sources are used, 100 percent of final summaries include the completion severity and source file for each affected patch.
- **SC-006**: Cleanup summaries include before/after splat counts for 100 percent of cleaned patches where counts can be determined.
- **SC-007**: If final SOG export fails after a valid merge, the run record identifies the merged cleaned PLY as valid and final SOG as failed in 100 percent of tested cases.
- **SC-008**: Public example configs and feature docs contain zero private local machine paths.

## Assumptions

- Feature 1 run records, config loading, CLI overrides, tool validation, and up-front resume/overwrite machinery are already available.
- Feature 3 has produced patch directories, training statuses, and patch splat outputs in the active run directory.
- The evidenced coral cleanup defaults are `max_area: 0.004`, `min_neighbors: 20`, `radius: 0.05`, `filter_boundaries: true`, and `boundary_buffer: 0.1`.
- Ordinary cleaned patch merging is required for the main pipeline and is separate from future mega-patching, NanoGS, streamed LOD, and PlayCanvas packaging.
- Per-patch SOG export is not part of the default main pipeline for this feature; the default SOG output is created from the merged cleaned site splat.
