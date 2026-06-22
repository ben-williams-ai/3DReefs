# Feature Specification: Optional Image Recolour Workflow

**Feature Branch**: `010-image-recolour-workflow`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "Add an optional Wildflow-style colour restoration workflow to the reef reconstruction pipeline. Audit and standardise image ordering first; add mandatory `recolour_images` and `project.start_sfm_immediately` configuration; allow users to tune keyframe colour parameters in a desktop GUI; preserve and resume GUI state; write corrected images next to raw images without modifying raw data; run SfM on raw images; apply the raw-image reconstruction geometry to the corrected image set for the final undistorted LFS handoff; preserve multi-camera folder semantics; treat the provided Wildflow script as the source of truth for colour operation order, neutral defaults, interpolation behaviour, and image-output preservation; and add focused tests for ordering, keyframes, state, correction outputs, undistortion handoff, and failure/waiting behaviour."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Run The Existing Pipeline Unchanged By Default (Priority: P1)

As a reconstruction user, I want the pipeline to keep its current behaviour unless I explicitly enable colour restoration, so existing datasets and experiments remain comparable.

**Why this priority**: Backward compatibility protects existing runs, experiment comparisons, and operational confidence.

**Independent Test**: Run a representative pipeline configuration with colour restoration disabled and verify the same raw-image SfM, normal undistortion output, and LFS handoff behaviour are used.

**Acceptance Scenarios**:

1. **Given** a configuration with colour restoration disabled, **When** the pipeline reaches reconstruction and splatting, **Then** SfM, undistortion, patching, and LFS consume the same image roots and handoff paths as before.
2. **Given** a configuration file missing only user-tuned colour state, **When** colour restoration is disabled, **Then** the pipeline does not open the colour GUI, does not create recoloured images, and does not wait for colour restoration.

---

### User Story 2 - Recolour Images While Preserving Raw SfM Geometry (Priority: P1)

As a reconstruction user, I want to colour-correct the image set for splatting while keeping SfM and camera estimation based on the original raw images, so geometry remains stable and the visual training inputs improve.

**Why this priority**: This is the core feature outcome and the main correctness risk, especially for COLMAP undistortion and multi-camera data.

**Independent Test**: Enable colour restoration, complete a colour-correction run, and verify raw images are used for SfM while the final standard undistorted image folder contains corrected images generated with the raw-image reconstruction.

**Acceptance Scenarios**:

1. **Given** colour restoration is enabled, **When** SfM runs, **Then** it uses the original raw image folder and never the corrected image folder.
2. **Given** colour restoration is complete, **When** the final undistortion handoff is produced, **Then** the standard undistorted image folder contains undistorted corrected images and the standard sparse handoff remains consistent with them.
3. **Given** multi-camera images organised by top-level camera folders, **When** corrected images and undistorted handoff outputs are produced, **Then** camera folder relationships, filenames, camera assignments, and relative paths remain matched to the raw-image reconstruction.

---

### User Story 3 - Tune And Resume Keyframe Colour Edits (Priority: P2)

As a user correcting underwater imagery, I want a simple desktop GUI to tune a small set of ordered keyframes, save edits continuously, and resume after interruptions, so long reconstruction runs do not lose manual work.

**Why this priority**: The feature depends on manual tuning, and resilience matters because SfM and splatting jobs can be long-running.

**Independent Test**: Open the GUI on a dataset, edit and save keyframes, close or simulate a failure, reopen the same run, and verify keyframes, saved values, status, and current position are restored.

**Acceptance Scenarios**:

1. **Given** the GUI opens for a new run, **When** keyframes are selected, edited, overwritten, deleted, or rebuilt, **Then** the saved state is updated immediately after each action.
2. **Given** a previous incomplete colour restoration state exists, **When** the same run is resumed, **Then** the GUI restores saved keyframes, edited markers, selected mode, recent keyframe where available, and completion status.
3. **Given** the user closes the GUI before completing colour restoration, **When** they choose to cancel, skip colour restoration, or continue editing, **Then** the pipeline state and saved status reflect that choice unambiguously.

---

### User Story 4 - Apply Interpolated Corrections To The Dataset (Priority: P2)

As a user, I want saved keyframe settings to be interpolated across the ordered image sequence and applied to every image, so the corrected image set is complete and reproducible.

**Why this priority**: Full-dataset application turns manual keyframe edits into usable training images and must preserve raw data safely.

**Independent Test**: Save edits on selected keyframes, apply colour restoration, and verify all expected images are written to the corrected image root with matching filenames, relative folders, and dimensions.

**Acceptance Scenarios**:

1. **Given** edited keyframes in one global sequence, **When** full-dataset correction is applied, **Then** the system interpolates parameters by robust image order and writes one corrected image for every source image.
2. **Given** "edit separately by camera" is enabled, **When** full-dataset correction is applied, **Then** keyframe selection and interpolation are performed independently per camera folder.
3. **Given** some listed keyframes are not edited, **When** the user applies correction, **Then** the system warns how many keyframes are unedited, how many images will be processed, and how many edited keyframes will drive interpolation before proceeding.

---

### User Story 5 - Use Robust Dataset Image Ordering (Priority: P2)

As a user processing camera sequences, I want all sequence-sensitive operations to use one clear ordering strategy, so filenames such as `img1`, `img2`, and `img10` are handled correctly and consistently.

**Why this priority**: Ordering affects SfM image lists, camera grouping, holdouts, patches, LFS handoff, and colour interpolation.

**Independent Test**: Run ordering checks on representative filename and multi-camera layouts and verify sequence-sensitive features use capture order when available and natural filename order otherwise.

**Acceptance Scenarios**:

1. **Given** images with reliable capture timestamps, **When** a sequence-sensitive operation requests dataset order, **Then** the images are ordered by capture time with stable tie-breaking.
2. **Given** images without reliable capture timestamps, **When** a sequence-sensitive operation requests dataset order, **Then** filenames and relative paths are ordered naturally rather than lexicographically.
3. **Given** multi-camera folders, **When** global and per-camera sequences are built, **Then** the ordering method and grouping are recorded and reused consistently.

### Edge Cases

- Too few images exist to avoid selecting image 0 as a keyframe.
- Capture timestamps are missing, duplicated, inconsistent across cameras, or unavailable for some images.
- Multi-camera folder names or filenames contain natural-number components that would sort incorrectly lexicographically.
- Colour restoration is enabled but the GUI cannot open.
- No keyframes have saved edits when the user attempts to apply colour restoration.
- Only one keyframe has saved edits when the user applies colour restoration.
- Images appear before the first edited keyframe or after the last edited keyframe in the ordered sequence.
- SfM fails while the colour GUI is open and edits have already been saved.
- Full-dataset colour correction fails part-way through an image batch.
- Corrected output already exists from a completed or partial prior run.
- The pipeline reaches splatting before colour restoration is complete.
- A user chooses to continue without colour restoration after having partially edited keyframes.
- A corrected image is missing, renamed, dimensionally different, or not aligned with the raw reconstruction image names.
- Source images have JPEG or non-JPEG extensions whose output format expectations differ.
- Preview images are downscaled for responsiveness but final outputs must remain full resolution.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST include a mandatory `recolour_images` configuration option with a default value of disabled.
- **FR-002**: The system MUST include a `project.start_sfm_immediately` configuration option with a default value of enabled.
- **FR-003**: When colour restoration is disabled, the system MUST preserve the existing pipeline behaviour for preflight, SfM, undistortion, patching, LFS handoff, and evaluation.
- **FR-004**: When colour restoration is enabled, the system MUST run normal preflight checks before colour restoration or SfM work begins.
- **FR-005**: When colour restoration is enabled and immediate SfM is enabled, the system MUST start raw-image SfM while the colour restoration GUI is available for user tuning.
- **FR-006**: When colour restoration is enabled and immediate SfM is disabled, the system MUST wait for colour restoration to complete or be explicitly skipped before starting SfM.
- **FR-007**: The system MUST always run SfM and reconstruction from the original raw images, regardless of colour restoration state.
- **FR-008**: The system MUST never edit, resize, rename, crop, overwrite, or delete raw images as part of colour restoration.
- **FR-009**: The system MUST write corrected raw-resolution images to a separate sibling image root, preserving exact filenames, dimensions, and relative folder structure.
- **FR-010**: The system MUST use the raw-image reconstruction geometry to produce the standard final undistorted handoff from corrected images when colour restoration is enabled and completed.
- **FR-011**: The system MUST ensure LFS and splatting consume the standard undistorted image and sparse handoff paths in both colour-restored and non-colour-restored runs.
- **FR-012**: The system MUST prevent splatting from silently continuing with raw or missing undistorted images when colour restoration is enabled and still incomplete.
- **FR-013**: The system MUST provide one robust image ordering strategy for all sequence-sensitive operations, preferring reliable capture order and falling back to natural ordering of relative filenames.
- **FR-014**: The system MUST record the image ordering method used for a colour restoration run in saved state.
- **FR-015**: The system MUST audit existing sequence-sensitive behaviours and update them to use the robust ordering strategy wherever order affects outcomes.
- **FR-016**: The system MUST select 10 keyframes by default, evenly spaced around bin centres rather than starting at image 0 when the image count allows.
- **FR-017**: Users MUST be able to change the keyframe count and rebuild keyframes without losing already saved edits unless they explicitly remove an edited keyframe.
- **FR-018**: Users MUST be able to choose whether keyframes and interpolation are global across the dataset or separate per camera folder.
- **FR-019**: The GUI MUST show raw and currently corrected previews for the selected keyframe and update the corrected preview when parameters change.
- **FR-020**: The GUI MUST expose the full valid control range for all specified colour parameters: grey-world correction, warmth, tint, saturation, blue reduction, brightness, contrast, shadows, blacks, highlights, dehaze strength, and dehaze omega.
- **FR-021**: The GUI MUST provide both slider and exact value entry controls for each colour parameter and keep those controls synchronised.
- **FR-022**: The GUI MUST let users navigate keyframes by previous/next buttons, direct index entry, and a clickable scrollable keyframe list.
- **FR-023**: The keyframe list MUST show global row index, camera folder, global dataset position, per-camera position, one-parent-folder filename, delete control, edit status or saved values, and a raw thumbnail.
- **FR-024**: The GUI MUST visually distinguish edited keyframes from unedited keyframes and allow deletion only after confirmation.
- **FR-025**: The system MUST save colour restoration state immediately after keyframes are created, edits are saved or overwritten, keyframes are deleted, mode changes are applied, and completion/skipped/cancelled status changes.
- **FR-026**: Saved state MUST include selected keyframes, image ordering method, camera edit mode, saved parameters, enough interpolation information to reproduce results, recent GUI position where useful, raw and corrected image roots, undistortion handoff roots, status, timestamp, and relevant configuration values.
- **FR-027**: Reruns of the same run MUST resume incomplete colour restoration state by default and MUST avoid overwriting completed corrected outputs unless the user or configuration explicitly allows it.
- **FR-028**: When applying correction to the full dataset, the system MUST warn before proceeding if not all listed keyframes have saved edits.
- **FR-029**: Full-dataset correction MUST report overall progress with total image counts in the GUI and terminal/log output.
- **FR-030**: If the GUI cannot open while colour restoration is enabled, the system MUST fail early with a clear error and MUST NOT continue to later stages that depend on corrected images.
- **FR-031**: If a pipeline stage fails while GUI work is in progress, the system MUST preserve saved GUI state and close or stop GUI work cleanly where possible.
- **FR-032**: If full-dataset correction fails part-way through, the system MUST report the failing image and exception, record an incomplete state, and MUST NOT continue with incomplete corrected outputs.
- **FR-033**: The GUI MUST offer explicit close choices before completion: cancel the job, continue without colour restoration, or return to editing.
- **FR-034**: If the user chooses to continue without colour restoration, the run MUST be marked as skipped and continue using the normal non-colour-restored handoff behaviour.
- **FR-035**: The system MUST include tests or documented checks for robust ordering, keyframe selection and preservation, state saving and resumption, per-camera mode, interpolation, output structure and dimensions, corrected-image undistortion handoff, LFS input paths, skip behaviour, GUI-open failure, and splatting wait/failure behaviour.
- **FR-036**: The colour correction operations and their order MUST match the provided Wildflow script exactly: grey-world correction, warmth, tint, saturation, blue reduction, brightness and contrast together, shadows, blacks, highlights, and dehaze.
- **FR-037**: Unless the provided Wildflow script defines different defaults, new and unedited keyframes MUST use these neutral defaults: grey-world correction `0.0`, warmth `0.0`, tint `0.0`, saturation `1.0`, blue reduction `0.0`, brightness `0.0`, contrast `0.0`, shadows `0.0`, blacks `0.0`, highlights `0.0`, dehaze strength `0.0`, and dehaze omega `0.9`.
- **FR-038**: The system MUST treat saturation as neutral at `1.0`; brightness, contrast, warmth, and tint as neutral at `0.0`; grey-world correction, blue reduction, shadows, blacks, highlights, and dehaze strength as off at `0.0`; and dehaze omega as relevant only when dehaze strength is above `0.0`.
- **FR-039**: The system MUST interpolate each numeric colour parameter independently using linear interpolation between saved keyframes.
- **FR-040**: For images before the first edited keyframe, the system MUST use the first edited keyframe's parameter set; for images after the last edited keyframe, it MUST use the last edited keyframe's parameter set.
- **FR-041**: If exactly one keyframe has saved edits, the system MUST apply that one parameter set to every image selected for colour restoration.
- **FR-042**: If no keyframes have saved edits, the system MUST NOT apply colour restoration and MUST warn or fail clearly according to the user action that attempted to proceed.
- **FR-043**: Corrected final outputs MUST be RGB images, preserve dimensions exactly, preserve relative path and filename exactly, and preserve the source extension where possible.
- **FR-044**: JPEG corrected outputs MUST use high-quality saving, with quality around 95 unless an existing project image-output convention specifies another high-quality value.
- **FR-045**: Preview and thumbnail images MAY be downscaled for GUI responsiveness, but the system MUST ensure downscaled preview data is never saved as a final corrected dataset image.

### Key Entities *(include if feature involves data)*

- **Image Sequence**: Ordered collection of raw images with relative paths, optional camera folder grouping, capture-order metadata where available, and natural-order fallback information.
- **Camera Group**: A top-level camera folder and its ordered subset of images, preserving the folder-based intrinsics relationship used by the reconstruction pipeline.
- **Keyframe**: A selected image in the global or per-camera sequence with positions, relative path, edit status, thumbnail reference, and optional saved colour parameters.
- **Colour Parameter Set**: Values for grey-world correction, warmth, tint, saturation, blue reduction, brightness, contrast, shadows, blacks, highlights, dehaze strength, and dehaze omega, using the neutral defaults and operation meanings defined by the Wildflow source behaviour.
- **Colour Restoration State**: Persistent run record containing keyframes, saved parameter sets, ordering method, edit mode, paths, status, progress, and reproducibility metadata.
- **Corrected Image Set**: Raw-resolution colour-corrected image tree that mirrors the raw image tree without modifying raw images.
- **Undistorted Handoff**: Standard final image and sparse reconstruction handoff consumed by downstream splatting and evaluation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Existing non-colour-restored pipeline runs complete with no additional user interaction and no changed output handoff paths.
- **SC-002**: For a 1,000-image sequence with 10 default keyframes, selected keyframe positions are centred within evenly spaced bins, such as approximately 50, 150, 250, 350, 450, 550, 650, 750, 850, and 950.
- **SC-003**: For a dataset containing `img1`, `img2`, and `img10`, all sequence-sensitive operations place `img2` before `img10` when capture timestamps are unavailable.
- **SC-004**: After a saved-edit interruption and rerun, 100% of previously saved keyframe parameter values and edited/un-edited markers are restored for the same run.
- **SC-005**: Full-dataset colour restoration writes exactly one corrected output image for every source image, with 100% matching relative paths, filenames, and dimensions.
- **SC-006**: In colour-restored runs, downstream splatting receives the standard undistorted handoff path and at least one verification check confirms those undistorted images derive from the corrected image root.
- **SC-007**: When the pipeline reaches splatting before colour restoration is complete, it emits a clear waiting message and does not proceed until the run is completed or explicitly skipped.
- **SC-008**: If colour restoration cannot start or fails part-way, the run fails before splatting and reports the actionable error, failed image where applicable, and saved state location.
- **SC-009**: Users can complete the primary GUI flow of selecting keyframes, saving edits, applying correction, and closing the completion prompt without overlapping controls or unusable navigation at the minimum supported window size.
- **SC-010**: A dataset processed with a single edited keyframe receives that exact parameter set for 100% of corrected output images.
- **SC-011**: In a sequence with edited first and last keyframes, at least three sampled intermediate images show independently linearly interpolated numeric parameter values between those two edits.
- **SC-012**: Corrected JPEG outputs retain their source dimensions and extension for 100% of processed images and are saved at high visual quality.

## Assumptions

- Users run this workflow on local workstations with access to the dataset image roots and a graphical desktop session when colour restoration is enabled.
- Existing run output locations remain the authoritative place for run-specific state and reproducibility records.
- Reliable capture timestamps are preferred only when they are present and consistent enough to define a meaningful sequence; otherwise natural ordering of relative paths is the expected fallback.
- A sibling corrected image root named for recoloured images is the default output location unless existing project configuration defines a clearer run-specific convention.
- Colour restoration is optional per run; users may explicitly skip it after partial editing and continue with normal non-colour-restored behaviour.
- The feature is scoped to preserving the existing standard downstream handoff rather than adding a separate downstream mode for corrected images.
- The provided Wildflow script remains the behavioural source of truth for colour operations, operation order, and supported parameter ranges.
- Final corrected dataset images are always generated from full-resolution source images even when GUI previews use lower-resolution representations for speed.
