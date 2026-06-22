# Feature Specification: Optional Image Recolour Workflow

**Feature Branch**: `010-image-recolour-workflow`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "Add an optional Wildflow-style colour restoration workflow to the reef reconstruction pipeline. Audit and standardise image ordering first; add mandatory `recolour_images` and `project.start_sfm_immediately` configuration; allow users to tune keyframe colour parameters in a desktop GUI; preserve and resume GUI state; write corrected images next to raw images without modifying raw data; run SfM on raw images; allow users to review corrected outputs and reopen the colour GUI to continue editing; support running colour restoration as an isolated command outside the full pipeline; apply the raw-image reconstruction geometry to the corrected image set for the final undistorted LFS handoff; preserve multi-camera folder semantics; treat the provided Wildflow script as the source of truth for colour operation order, neutral defaults, interpolation behaviour, and image-output preservation; and add focused tests for ordering, keyframes, state, correction outputs, undistortion handoff, reopening/resume behaviour, standalone colour restoration, and failure/waiting behaviour."

## User Scenarios & Testing *(mandatory)*

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
4. **Given** a user is tuning a keyframe, **When** they adjust colour values, type exact values, move between keyframes, or use the keyframe list, **Then** the GUI remains usable, scrollable where needed, and shows both the raw image and the current corrected preview.

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
4. **Given** image order affects reconstruction lists, camera folder handling, patch selection, LFS handoff, evaluation holdouts, or colour keyframe interpolation, **When** that operation selects or compares images, **Then** it uses the shared ordering strategy rather than a local ad hoc sort.

---

### User Story 6 - Review And Continue Colour Corrections (Priority: P2)

As a user, I want to inspect corrected images after an initial full-dataset correction and then reopen the colour GUI to continue editing from the saved state, so I can improve bad areas before splatting starts.

**Why this priority**: Colour restoration is an iterative visual task; users need a way to correct mistakes after seeing the full corrected dataset without restarting from scratch.

**Independent Test**: Complete a colour restoration pass, close the GUI, reopen the same run through the documented command, add or update keyframe edits, reapply correction, and verify splatting waits while the reopened GUI session is active.

**Acceptance Scenarios**:

1. **Given** SfM is configured to start immediately, **When** colour restoration starts, completes, is reopened, or is edited again, **Then** SfM may continue in the background on raw images and is not blocked by the user reviewing colour outputs.
2. **Given** a completed or incomplete colour restoration state exists, **When** the user runs the documented colour GUI command for that run, **Then** the GUI reopens with previous keyframes, edits, mode, and output paths restored.
3. **Given** a colour GUI session is open or a colour correction apply operation is in progress, **When** the pipeline is ready to begin splatting, **Then** splatting waits until the GUI session is closed and the colour state is complete or explicitly skipped.
4. **Given** the user wants to do colour restoration without running the full reconstruction pipeline, **When** they run the documented standalone colour restoration command, **Then** they can select, save, resume, and apply colour corrections using the same saved state rules.

---

### User Story 7 - Fail Safely And Resume Work (Priority: P2)

As a user running long reef reconstruction jobs, I want colour restoration failures, pipeline failures, and reruns to preserve my work and stop unsafe downstream processing, so a problem does not waste hours or silently produce invalid splatting inputs.

**Why this priority**: The original workflow can run for a long time, and colour restoration introduces manual state and generated image outputs that must not be lost, half-used, or confused with completed results.

**Independent Test**: Simulate GUI start failure, pipeline failure while edits exist, partial full-dataset correction failure, and a rerun of the same run; verify saved state is preserved, errors are clear, incomplete outputs are not consumed, and reruns resume or require an explicit user choice.

**Acceptance Scenarios**:

1. **Given** colour restoration is enabled, **When** the GUI cannot open, **Then** the run fails early with a clear error before downstream stages depend on corrected images.
2. **Given** SfM or another pipeline stage fails while colour edits have been saved, **When** the user reruns the same run, **Then** the colour GUI can resume from the saved edits rather than starting over.
3. **Given** full-dataset colour correction fails part-way through, **When** the pipeline reaches later stages, **Then** incomplete corrected outputs are not used and the user sees which image or action failed.
4. **Given** corrected outputs already exist, **When** a rerun or reopened GUI would write outputs again, **Then** the user gets safe resume, review, or overwrite behaviour rather than accidental data replacement.
5. **Given** the user chooses to cancel or skip colour restoration, **When** the pipeline continues or stops, **Then** the saved run state clearly records that choice.

---

### User Story 8 - Correct Multi-Camera Datasets Deliberately (Priority: P2)

As a user processing one or more camera folders, I want colour restoration to support both shared dataset-wide edits and separate per-camera edits, so cameras with different colour casts can be corrected without breaking reconstruction relationships.

**Why this priority**: The pipeline relies on folder-based camera grouping, and multi-camera colour differences are likely in reef capture workflows.

**Independent Test**: Run colour restoration on a dataset with multiple camera folders, switch between global and per-camera modes, save edits for each mode, apply correction, and verify output images preserve camera folder structure and camera-specific correction behaviour.

**Acceptance Scenarios**:

1. **Given** separate-by-camera mode is off, **When** keyframes are selected, **Then** the user gets one ordered keyframe sequence across the dataset.
2. **Given** separate-by-camera mode is on, **When** keyframes are selected, **Then** each camera folder gets its own ordered keyframe sequence and interpolation scope.
3. **Given** one, two, or more camera folders exist, **When** colour correction is applied, **Then** the corrected output preserves each camera folder and does not mix camera-specific image identities.
4. **Given** a user changes the separate-by-camera mode, **When** existing edited keyframes still refer to valid images, **Then** saved edits are preserved unless the user explicitly removes them.

---

### User Story 9 - Make Informed Apply And Exit Decisions (Priority: P3)

As a user, I want clear prompts and progress feedback when applying or leaving colour restoration, so I understand whether corrections are complete, skipped, cancelled, or still waiting for action.

**Why this priority**: Colour restoration is manual and can affect long downstream jobs; ambiguous prompts could cause users to accidentally continue with the wrong image set.

**Independent Test**: Try applying with all keyframes edited, applying with unedited keyframes, cancelling an apply confirmation, closing before completion, and completing a full correction; verify the user sees clear counts, choices, progress, completion status, and next-step messaging.

**Acceptance Scenarios**:

1. **Given** not all listed keyframes have saved edits, **When** the user chooses to apply colour restoration, **Then** the confirmation explains how many keyframes are unedited, how many images will be corrected, and how many edited keyframes will drive interpolation.
2. **Given** all listed keyframes have saved edits, **When** the user chooses to apply colour restoration, **Then** the confirmation clearly states the number of images that will be corrected.
3. **Given** full-dataset correction is running, **When** the user watches progress, **Then** the GUI and terminal output show overall progress for the whole dataset.
4. **Given** colour restoration completes, **When** the user sees the completion state, **Then** the GUI explains that SfM may already be running or will start if it has not already.
5. **Given** the user closes the GUI before completion, **When** they choose cancel, skip, or return to editing, **Then** the run follows that exact choice and records it in saved state.

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
- The pipeline reaches splatting while a reopened colour GUI session is active after a previous completion.
- The user reopens a completed colour restoration run, changes keyframes, and applies a new corrected image set.
- The user runs colour restoration in isolation without requesting SfM, patching, or splatting.
- The user switches between shared dataset-wide edits and separate per-camera edits after saving some keyframes.
- The user cancels an apply confirmation after seeing unedited keyframe counts.
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
- **FR-012**: The system MUST NOT use a separate LFS-specific undistortion path for normal colour-restored runs; downstream stages must see the standard handoff.
- **FR-013**: The system MUST prevent splatting from silently continuing with raw or missing undistorted images when colour restoration is enabled and still incomplete.
- **FR-014**: The system MUST prevent splatting from starting while any colour restoration GUI session is active or any full-dataset colour correction apply operation is in progress.
- **FR-015**: The system MUST provide one robust image ordering strategy for all sequence-sensitive operations, preferring reliable capture metadata when available and falling back to natural ordering of relative filenames.
- **FR-016**: The shared ordering strategy MUST cover reconstruction image lists, multi-camera folder handling, patch image selection, LFS handoff, evaluation or holdout ordering, and colour restoration keyframe selection and interpolation.
- **FR-017**: The system MUST record the image ordering method used for a colour restoration run in saved state.
- **FR-018**: The system MUST audit existing sequence-sensitive behaviours and update them to use the robust ordering strategy wherever order affects outcomes.
- **FR-019**: The system MUST select 10 keyframes by default, evenly spaced around bin centres rather than starting at image 0 when the image count allows.
- **FR-020**: Users MUST be able to change the keyframe count and rebuild keyframes without losing already saved edits unless they explicitly remove an edited keyframe.
- **FR-021**: Users MUST be able to choose whether keyframes and interpolation are global across the dataset or separate per camera folder.
- **FR-022**: The GUI MUST show raw and currently corrected previews for the selected keyframe and update the corrected preview when parameters change.
- **FR-023**: The GUI MUST expose the full valid control range for all specified colour parameters: grey-world correction, warmth, tint, saturation, blue reduction, brightness, contrast, shadows, blacks, highlights, dehaze strength, and dehaze omega.
- **FR-024**: The GUI MUST provide both slider and exact value entry controls for each colour parameter and keep those controls synchronised.
- **FR-025**: The GUI MUST let users navigate keyframes by previous/next buttons, direct index entry, and a clickable scrollable keyframe list.
- **FR-026**: The keyframe list MUST show row order, camera folder, dataset position, per-camera position, nearby filename context, deletion control, edit status or saved values, and a raw thumbnail.
- **FR-027**: The GUI MUST visually distinguish edited keyframes from unedited keyframes and allow deletion only after confirmation.
- **FR-028**: The GUI MUST support a normal, resizable desktop window with scrollable controls or lists where needed, visible progress during full-dataset correction, and clear close or minimise behaviour.
- **FR-029**: The system MUST provide a documented command that reopens the colour restoration GUI for an existing run and resumes from the saved colour restoration state.
- **FR-030**: The colour restoration workflow MUST be runnable as a documented standalone command so users can perform keyframe selection, editing, state saving, resumption, and full-dataset correction without running the rest of the reconstruction pipeline.
- **FR-031**: Reopening a completed colour restoration run MUST allow users to continue editing, update or add keyframe edits, and reapply full-dataset colour restoration without losing prior saved work.
- **FR-032**: When a completed colour restoration run is reopened for further edits, its state MUST clearly indicate that a review or edit session is active until the user completes, skips, or closes that session.
- **FR-033**: The system MUST save colour restoration state immediately after keyframes are created, edits are saved or overwritten, keyframes are deleted, mode changes are applied, session activity changes, and completion/skipped/cancelled status changes.
- **FR-034**: Saved state MUST include selected keyframes, image ordering method, camera edit mode, saved parameters, enough interpolation information to reproduce results, recent GUI position where useful, raw and corrected image roots, undistortion handoff roots, status, active-session state, timestamp, and relevant configuration values.
- **FR-035**: Reruns of the same run MUST resume incomplete colour restoration state by default and MUST avoid overwriting completed corrected outputs unless the user or configuration explicitly allows it.
- **FR-036**: When applying correction to the full dataset, the system MUST warn before proceeding if not all listed keyframes have saved edits.
- **FR-037**: Full-dataset correction MUST report overall progress with total image counts in the GUI and terminal/log output.
- **FR-038**: Colour restoration SHOULD use available local acceleration when present, while still completing correctly on systems without acceleration.
- **FR-039**: If the GUI cannot open while colour restoration is enabled, the system MUST fail early with a clear error and MUST NOT continue to later stages that depend on corrected images.
- **FR-040**: If a pipeline stage fails while GUI work is in progress, the system MUST preserve saved GUI state and close or stop GUI work cleanly where possible.
- **FR-041**: If full-dataset correction fails part-way through, the system MUST report the failing image and exception, record an incomplete state, and MUST NOT continue with incomplete corrected outputs.
- **FR-042**: The GUI MUST offer explicit close choices before completion: cancel the job, continue without colour restoration, or return to editing.
- **FR-043**: If the user chooses to continue without colour restoration, the run MUST be marked as skipped and continue using the normal non-colour-restored handoff behaviour.
- **FR-044**: Project documentation MUST explain the colour restoration workflow, background SfM behaviour, how to inspect corrected outputs, how to reopen the GUI to continue editing, how splatting waits while the GUI is active, and how to run colour restoration in isolation.
- **FR-045**: The system MUST include tests or documented checks for robust ordering, keyframe selection and preservation, state saving and resumption, per-camera mode, interpolation, output structure and dimensions, corrected-image undistortion handoff, LFS input paths, skip behaviour, GUI-open failure, reopened GUI waiting behaviour, standalone colour restoration, and splatting wait/failure behaviour.
- **FR-046**: The colour correction operations and their order MUST match the provided Wildflow script exactly: grey-world correction, warmth, tint, saturation, blue reduction, brightness and contrast together, shadows, blacks, highlights, and dehaze.
- **FR-047**: Unless the provided Wildflow script defines different defaults, new and unedited keyframes MUST use these neutral defaults: grey-world correction `0.0`, warmth `0.0`, tint `0.0`, saturation `1.0`, blue reduction `0.0`, brightness `0.0`, contrast `0.0`, shadows `0.0`, blacks `0.0`, highlights `0.0`, dehaze strength `0.0`, and dehaze omega `0.9`.
- **FR-048**: The system MUST treat saturation as neutral at `1.0`; brightness, contrast, warmth, and tint as neutral at `0.0`; grey-world correction, blue reduction, shadows, blacks, highlights, and dehaze strength as off at `0.0`; and dehaze omega as relevant only when dehaze strength is above `0.0`.
- **FR-049**: The system MUST interpolate each numeric colour parameter independently using linear interpolation between saved keyframes.
- **FR-050**: For images before the first edited keyframe, the system MUST use the first edited keyframe's parameter set; for images after the last edited keyframe, it MUST use the last edited keyframe's parameter set.
- **FR-051**: If exactly one keyframe has saved edits, the system MUST apply that one parameter set to every image selected for colour restoration.
- **FR-052**: If no keyframes have saved edits, the system MUST NOT apply colour restoration and MUST warn or fail clearly according to the user action that attempted to proceed.
- **FR-053**: Corrected final outputs MUST be RGB images, preserve dimensions exactly, preserve relative path and filename exactly, preserve the source extension where possible, and use high-quality saving for lossy formats.
- **FR-054**: Preview and thumbnail images MAY be downscaled for GUI responsiveness, but the system MUST ensure downscaled preview data is never saved as a final corrected dataset image.

### Key Entities *(include if feature involves data)*

- **Image Sequence**: Ordered collection of raw images with relative paths, optional camera folder grouping, capture-order metadata where available, and natural-order fallback information.
- **Camera Group**: A top-level camera folder and its ordered subset of images, preserving the folder-based intrinsics relationship used by the reconstruction pipeline.
- **Keyframe**: A selected image in the global or per-camera sequence with positions, relative path, edit status, thumbnail reference, and optional saved colour parameters.
- **Colour Parameter Set**: Values for grey-world correction, warmth, tint, saturation, blue reduction, brightness, contrast, shadows, blacks, highlights, dehaze strength, and dehaze omega, using the neutral defaults and operation meanings defined by the Wildflow source behaviour.
- **Colour Restoration State**: Persistent run record containing keyframes, saved parameter sets, ordering method, edit mode, paths, status, progress, and reproducibility metadata.
- **Colour Restoration Session**: An active GUI or standalone colour correction session associated with a run, used to distinguish completed outputs that are available for review from outputs currently being edited.
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
- **SC-013**: Sequence-sensitive operations covered by the ordering audit use the shared ordering strategy or document why order is irrelevant.
- **SC-014**: In colour-restored runs, the pipeline never reaches splatting with incomplete colour restoration unless the user explicitly chooses to skip it.
- **SC-015**: After a completed colour restoration run is reopened, the GUI restores previous state and allows a new corrected image set to be applied without requiring the user to recreate earlier keyframe edits.
- **SC-016**: If splatting is ready while the colour GUI is open, splatting waits and emits a clear message in 100% of tested colour-restored runs.
- **SC-017**: A documented standalone colour restoration command lets users complete the colour correction workflow without invoking SfM, patching, or splatting.
- **SC-018**: The README documents the colour restoration workflow, reopen command, standalone command, corrected-output review step, and splatting wait behaviour.
- **SC-019**: In a multi-camera dataset, global and separate-by-camera modes both preserve 100% of camera folder paths and do not mix image identities across camera folders.
- **SC-020**: Apply and close prompts present the required counts, choices, and completion or skip/cancel status in 100% of tested prompt paths.

## Assumptions

- Users run this workflow on local workstations with access to the dataset image roots and a graphical desktop session when colour restoration is enabled.
- Existing run output locations remain the authoritative place for run-specific state and reproducibility records.
- Reliable capture timestamps are preferred only when they are present and consistent enough to define a meaningful sequence; otherwise natural ordering of relative paths is the expected fallback.
- A sibling corrected image root named for recoloured images is the default output location unless existing project configuration defines a clearer run-specific convention.
- Colour restoration is optional per run; users may explicitly skip it after partial editing and continue with normal non-colour-restored behaviour.
- Users may review corrected outputs after an apply operation and decide to reopen the GUI for more edits before allowing splatting to continue.
- The feature is scoped to preserving the existing standard downstream handoff rather than adding a separate downstream mode for corrected images.
- The provided Wildflow script remains the behavioural source of truth for colour operation behaviour, operation order, and supported parameter ranges; implementation-specific library choices belong in the planning phase.
- Final corrected dataset images are always generated from full-resolution source images even when GUI previews use lower-resolution representations for speed.
