# Feature Specification: COLMAP SfM Pipeline

**Feature Branch**: `002-colmap-sfm-pipeline`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: User description: "Create Feature 2: COLMAP SfM Pipeline for 3DReefs. Cover the COLMAP SfM part only: raw-image SfM, image/data checks, intrinsics handling, feature extraction, matching, reconstruction, undistortion, optional dense/mesh, COLMAP logging/timing, and up-front resume/overwrite decisions. Exclude splat outlier filtering, patching, LFS training, cleanup, SOG compression, splat merging, NanoGS, LOD, PlayCanvas packaging, and mega-patching."

## Clarifications

### Session 2026-06-10

- Q: How should invalid recoloured-image inputs be handled when recoloured-image use is enabled? → A: Fail during preflight before any heavy SfM work starts wherever possible.
- Q: How should intrinsics pre-calculation behave when there are too few images for the normal default selection window? → A: Use all suitable available images for that camera, warn clearly, and fail only if no valid calibration images are available.
- Q: How should the pipeline handle multiple sparse reconstruction models? → A: Automatically select the model with the most registered images, warn clearly, and record the registered image count and 3D point count for each produced model.
- Q: What should happen when selected matching requires a vocabulary tree but no valid vocabulary tree is available? → A: Fail during preflight before matching starts; the vocabulary tree must be a required config resource whenever a selected matching mode uses vocabulary-tree matching, including the default matching sequence.
- Q: How should preflight handle available metadata that suggests mixed camera sources within a camera group? → A: In interactive runs, prompt the researcher before any SfM stage starts, explain that the folder appears to contain different camera sources, and ask them to confirm all images are from the intended camera and unmodified; proceed only if they explicitly confirm, otherwise stop so they can check the data. In non-interactive runs, fail before SfM starts unless an explicit pre-supplied proceed setting is present.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Produce Sparse SfM Outputs Ready For Splatting (Priority: P1)

A reef reconstruction researcher can run the SfM portion of the pipeline from the existing project config and obtain a successful sparse reconstruction plus undistorted outputs that are ready for later splatting stages.

**Why this priority**: Sparse reconstruction and undistortion are the required bridge between the raw reef image collection and all later splatting work. Without this reliable handoff, patching and training cannot be trusted.

**Independent Test**: Can be tested with a valid project directory containing `raw_images/`, valid configured external tools, and a request to run the SfM stages only. The run should produce sparse reconstruction outputs, undistorted images, undistorted camera data, stage timings, and COLMAP logs without starting any splatting stage.

**Acceptance Scenarios**:

1. **Given** a valid project containing raw images, **When** the researcher runs the SfM stages, **Then** the system completes feature extraction, matching, reconstruction, and undistortion using raw images for SfM and records the produced sparse and undistorted outputs.
2. **Given** the run completes successfully, **When** the researcher inspects the run record, **Then** the record identifies the sparse reconstruction, undistorted images, undistorted sparse model, effective settings, tool validation results, command log, stage timings, and completion status.
3. **Given** the researcher later starts splatting work, **When** the pipeline selects SfM outputs, **Then** it uses the undistorted images and undistorted sparse model from the completed SfM run rather than the raw-image sparse intrinsics.

---

### User Story 2 - Validate Reef Image Inputs Before Heavy SfM Work (Priority: P2)

A researcher receives clear early feedback when image organisation, image dimensions, camera consistency, or optional recoloured-image inputs are unsuitable for a reliable SfM run.

**Why this priority**: Large reef datasets can take many hours to process. Detecting data problems before feature extraction or reconstruction avoids wasting compute and prevents confusing downstream failures.

**Independent Test**: Can be tested with small single-camera and multi-camera fixtures, including invalid layouts, mixed image dimensions, inconsistent camera metadata, and missing recoloured counterparts.

**Acceptance Scenarios**:

1. **Given** images directly inside `raw_images/`, **When** the researcher starts SfM, **Then** the system treats the project as single-camera unless an explicit camera mapping says otherwise.
2. **Given** one folder per camera inside `raw_images/`, **When** the researcher starts SfM, **Then** the system treats the project as multi-camera and reports image counts and dimensions per camera.
3. **Given** a camera folder contains images with more than one dimension, **When** preflight runs, **Then** the system fails before heavy SfM work and reports the distinct dimensions, counts, example images, and location of the full diagnostic record.
4. **Given** camera metadata is available and suggests mixed camera sources within a camera folder, **When** preflight checks camera consistency, **Then** the system warns before any SfM stage starts, explains the concern in beginner-friendly language, and asks the researcher to confirm whether all images are from the intended camera and unmodified.
5. **Given** camera metadata is missing or incomplete, **When** preflight checks camera consistency, **Then** the system reports the consistency status as unknown rather than failing solely because metadata is absent.
6. **Given** the researcher does not confirm a mixed-camera-source warning, **When** preflight receives that decision, **Then** the system stops before heavy SfM work so the researcher can check their data.
7. **Given** a non-interactive run has a mixed-camera-source warning and no explicit pre-supplied proceed setting, **When** preflight runs, **Then** the system fails before heavy SfM work starts.
8. **Given** recoloured images are enabled, **When** preflight runs, **Then** the system verifies that recoloured images mirror raw image relative paths, filenames, and dimensions for later undistortion use.

---

### User Story 3 - Control Intrinsics And Reconstruction Strategy (Priority: P3)

A researcher can use safe defaults for reef reconstruction while still choosing explicit intrinsics, matching, and reconstruction options when needed for experiments.

**Why this priority**: Reef datasets are often loop-heavy, multi-camera, and visually repetitive. The pipeline needs sensible defaults, but research runs must also be configurable and auditable.

**Independent Test**: Can be tested by running configurations that use default intrinsics pre-calculation, user-supplied camera files, supported matching choices, global reconstruction, and incremental reconstruction on small controlled datasets.

**Acceptance Scenarios**:

1. **Given** no user-supplied camera file, **When** SfM starts, **Then** the system pre-calculates intrinsics by default using the configured camera model and records which images were used for that calibration.
2. **Given** a user-supplied COLMAP-format camera file, **When** SfM starts, **Then** the system validates the file and uses it instead of pre-calculating intrinsics or applying the default camera model.
3. **Given** fixed or pre-calculated intrinsics are used, **When** reconstruction runs, **Then** intrinsics are not refined unless the researcher explicitly enables refinement.
4. **Given** the default matching configuration, **When** matching runs, **Then** the system performs sequence-based matching followed by retrieval-based loop/recovery matching and records both matching passes.
5. **Given** the researcher selects a supported alternative matching mode, **When** matching runs, **Then** only the selected matching strategy or named matching sequence is used and recorded.
6. **Given** the researcher selects spatial matching without valid pose priors, **When** preflight runs, **Then** the system fails clearly before matching begins.
7. **Given** the selected matching configuration includes vocabulary-tree matching, **When** preflight runs without a valid vocabulary tree resource, **Then** the system fails before matching starts and explains that the selected matching mode requires a vocabulary tree.
8. **Given** the default reconstruction configuration, **When** reconstruction runs, **Then** the system uses COLMAP's global reconstruction path and records that choice.
9. **Given** the researcher selects incremental reconstruction, **When** reconstruction runs, **Then** the system uses the incremental path and does not silently switch to global reconstruction or any legacy standalone backend.
10. **Given** reconstruction produces multiple sparse models, **When** the system selects the model for undistortion and downstream stages, **Then** it selects the model with the most registered images, warns clearly, and records the registered image count and 3D point count for every produced model.

---

### User Story 4 - Use Recoloured Images Only For Undistorted Splatting Inputs (Priority: P4)

A researcher can optionally provide recoloured images for later splatting while preserving raw-image SfM behaviour.

**Why this priority**: Underwater colour enhancement may improve splat appearance, but SfM should continue to use raw images for robust feature extraction and reconstruction.

**Independent Test**: Can be tested with a project where raw and recoloured images have matching layouts and filenames. The SfM stages should use raw images up to sparse reconstruction, then undistortion should use the selected image source according to the recoloured-image setting.

**Acceptance Scenarios**:

1. **Given** recoloured images are disabled, **When** undistortion runs, **Then** the system undistorts raw images.
2. **Given** recoloured images are enabled and valid, **When** undistortion runs, **Then** the system uses the raw-image reconstruction with the matching recoloured images to produce undistorted images for downstream splatting.
3. **Given** recoloured images are enabled but any required counterpart is missing, extra, or dimensionally inconsistent, **When** preflight runs, **Then** the system fails before SfM starts and reports the mismatch.
4. **Given** undistortion completes, **When** downstream stages inspect SfM outputs, **Then** they use the undistorted sparse intrinsics generated by undistortion rather than the original raw-image or user-supplied intrinsics.

---

### User Story 5 - Optionally Produce Dense And Mesh Outputs (Priority: P5)

A researcher can enable dense point cloud and mesh outputs for small-area comparisons while keeping these expensive outputs disabled by default.

**Why this priority**: Dense and mesh outputs are useful for selected experiments, but they are not required for the main splatting pipeline and should not consume time unexpectedly.

**Independent Test**: Can be tested with dense and mesh disabled by default, then enabled explicitly on a small dataset. The enabled run should record output presence, file sizes, and timings.

**Acceptance Scenarios**:

1. **Given** the default configuration, **When** SfM completes, **Then** dense point cloud and mesh generation do not run.
2. **Given** dense output is explicitly enabled, **When** sparse reconstruction and undistortion have completed, **Then** the system produces dense reconstruction outputs and records their timing and completion status.
3. **Given** mesh output is explicitly enabled, **When** dense prerequisites are available, **Then** the system produces mesh outputs and records their timing and completion status.
4. **Given** mesh output is enabled without the required dense output, **When** preflight runs, **Then** the system fails before heavy work and explains the missing prerequisite.

---

### User Story 6 - Resume Or Restart SfM Stages Explicitly (Priority: P6)

A researcher can resume or restart partially completed SfM work only after all prior outputs, completed stages, and setting differences are detected and resolved up front.

**Why this priority**: SfM stages are expensive and stateful. Silent reuse, silent overwrite, or mid-run prompts can make results irreproducible and waste days of compute.

**Independent Test**: Can be tested with simulated partial outputs for feature extraction, matching, reconstruction, undistortion, dense output, and mesh output. The next run should gather all required decisions before any requested stage starts.

**Acceptance Scenarios**:

1. **Given** a previous SfM run completed feature extraction but not matching, **When** the researcher starts SfM again, **Then** the system detects the partial state and asks whether to resume or start over before any stage runs.
2. **Given** a requested SfM stage already completed, **When** the researcher requests that stage again, **Then** the system asks up front whether to reuse, rerun, or overwrite the existing outputs.
3. **Given** multiple requested SfM stages have prior outputs, **When** preflight runs, **Then** the system resolves each required decision before starting the first stage.
4. **Given** the requested effective settings differ from a prior partial run, **When** preflight runs, **Then** the system reports the differences and records the decision before any stage runs.
5. **Given** a non-interactive run encounters prior partial or completed outputs without an explicit resume or overwrite policy, **When** preflight runs, **Then** the system fails before running any SfM stage.
6. **Given** an SfM run was interrupted during undistortion after reconstruction completed, **When** the researcher resumes that run by id and requests undistortion with overwrite, **Then** the system reuses the selected sparse model from that same run directory, removes the partial undistortion output, reruns undistortion, and updates the same run records.

### Edge Cases

- `raw_images/` mixes direct images with camera subfolders.
- A camera folder is empty or contains no supported image files.
- A camera folder contains images with multiple dimensions.
- Recoloured images are enabled but the folder is missing, incomplete, has extra unmatched files, or has different dimensions; the run fails during preflight before any heavy SfM work starts wherever possible.
- Optional EXIF checks are enabled but images lack useful metadata.
- Available metadata suggests one camera group may contain images from different camera sources.
- A non-interactive run encounters a mixed-camera-source warning without an explicit pre-supplied proceed setting.
- Optional EXIF pose-prior checks are enabled for an underwater dataset with no GPS data.
- A user-supplied camera file is missing, malformed, has the wrong number of cameras, or has dimensions that do not match raw images.
- Intrinsics pre-calculation has too few images to use the normal default selection window; the system uses all suitable available images for that camera, records a warning, and fails only if no valid calibration images are available.
- A selected matching mode requires unavailable supporting data.
- A selected matching mode uses vocabulary-tree matching but no valid vocabulary tree resource is configured.
- A selected reconstruction backend is unsupported by the configured external tool.
- The configured global reconstruction backend is unavailable and incremental reconstruction is available, or vice versa.
- Reconstruction produces multiple sparse models; the model with the most registered images is selected and all model image/point counts are recorded.
- A heavy SfM stage fails after writing partial outputs.
- Prior outputs exist but the previous run status is missing or inconsistent.
- Dense or mesh outputs are requested without the required prerequisite outputs.
- Public example configs or generated public docs accidentally include private local paths.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a researcher to run the SfM portion of the pipeline from the existing one-command config workflow.
- **FR-002**: The system MUST use raw images for feature extraction, matching, and sparse reconstruction.
- **FR-003**: The system MUST support both single-camera and multi-camera input layouts established by the pipeline foundation.
- **FR-004**: The system MUST validate image dimensions per camera before heavy SfM work begins.
- **FR-005**: The system MUST report camera-source consistency per camera when usable metadata is available, and report unknown rather than failing when metadata is unavailable.
- **FR-006**: When usable metadata suggests mixed camera sources within a camera group during an interactive run, the system MUST prompt the researcher before any SfM stage starts, explain the concern, and proceed only after explicit confirmation that the images are from the intended camera and unmodified.
- **FR-007**: When the researcher does not confirm a mixed-camera-source warning, the system MUST stop before heavy SfM work so the researcher can check their data.
- **FR-008**: When usable metadata suggests mixed camera sources within a camera group during a non-interactive run, the system MUST fail before SfM starts unless an explicit pre-supplied proceed setting is present.
- **FR-009**: The system MUST keep optional EXIF and pose-prior checks disabled by default for underwater reef datasets.
- **FR-010**: The system MUST allow optional EXIF and pose-prior checks for datasets where such metadata may be useful.
- **FR-011**: The system MUST validate recoloured images before SfM starts when recoloured-image use is enabled, and MUST fail before heavy SfM work if the recoloured collection does not mirror raw image relative paths, filenames, and dimensions.
- **FR-012**: The system MUST ensure recoloured images are not used for feature extraction, matching, or sparse reconstruction.
- **FR-013**: The system MUST use recoloured images for undistortion when recoloured-image use is enabled and validation passes.
- **FR-014**: The system MUST use raw images for undistortion when recoloured-image use is disabled.
- **FR-015**: The system MUST default to the OPENCV camera model when no user-supplied camera file overrides camera handling.
- **FR-016**: The system MUST pre-calculate intrinsics by default unless a valid user-supplied camera file is provided.
- **FR-017**: The system MUST record the images selected for intrinsics pre-calculation; when a camera has fewer images than the normal selection window, the system MUST use the suitable available images, warn clearly, and fail only when no valid calibration images are available.
- **FR-018**: The system MUST validate a user-supplied COLMAP-format camera file before using it.
- **FR-019**: A valid user-supplied camera file MUST override intrinsics pre-calculation and default camera model selection.
- **FR-020**: The system MUST keep intrinsics fixed during final reconstruction by default when fixed, pre-calculated, or user-supplied intrinsics are used.
- **FR-021**: The system MUST allow the researcher to explicitly enable intrinsics refinement for final reconstruction.
- **FR-022**: The system MUST use raw image dimensions for feature extraction by default.
- **FR-023**: The system MUST allow the researcher to override the maximum feature-extraction image size.
- **FR-024**: The system MUST default to the configured reef feature-count behaviour, including a lower protective feature count for very large image collections unless the researcher explicitly overrides it.
- **FR-025**: The system MUST default to sequential matching followed by vocabulary-tree matching.
- **FR-026**: The system MUST expose exhaustive, sequential, vocabulary-tree, spatial, sequential-plus-vocabulary-tree, and named hybrid matching choices as user-visible options.
- **FR-027**: The system MUST fail before matching when the selected matching mode requires supporting metadata that is unavailable.
- **FR-028**: The system MUST require a valid vocabulary tree resource in the config whenever the selected matching mode uses vocabulary-tree matching, including the default matching sequence.
- **FR-029**: The system MUST default to COLMAP's native global reconstruction path.
- **FR-030**: The system MUST allow the researcher to select COLMAP's classic incremental reconstruction path.
- **FR-031**: The system MUST NOT include or invoke a legacy standalone GLOMAP backend.
- **FR-032**: The system MUST NOT silently fall back between global and incremental reconstruction backends.
- **FR-033**: The system MUST validate that the selected reconstruction backend is available before heavy reconstruction starts.
- **FR-034**: The system MUST run image undistortion after successful sparse reconstruction.
- **FR-035**: When reconstruction produces multiple sparse models, the system MUST select the model with the most registered images for undistortion and downstream stages, warn clearly, and record the registered image count and 3D point count for each produced model.
- **FR-036**: The system MUST default undistorted images to a maximum dimension of 4096 while preserving aspect ratio and retaining smaller original dimensions where applicable.
- **FR-037**: The system MUST record and expose the undistorted sparse intrinsics for downstream stages.
- **FR-038**: The system MUST keep dense point cloud generation disabled by default.
- **FR-039**: The system MUST keep mesh generation disabled by default.
- **FR-040**: The system MUST allow dense point cloud generation and mesh generation to be enabled explicitly.
- **FR-041**: The system MUST fail before heavy work when mesh generation is requested without required dense prerequisites.
- **FR-042**: The system MUST log the SfM stages, selected options, warnings, completion status, and external command output in the run record.
- **FR-043**: The system MUST record exact timings for preflight, intrinsics pre-calculation, feature extraction, each matching pass, reconstruction, undistortion, dense generation, and mesh generation when those stages run.
- **FR-044**: The system MUST gather all resume, reuse, rerun, and overwrite decisions before any requested SfM stage starts.
- **FR-045**: The system MUST detect and report setting differences between requested SfM settings and prior partial SfM outputs before any requested stage starts.
- **FR-046**: The system MUST fail early in non-interactive contexts when prior SfM outputs require a decision and no explicit policy was supplied.
- **FR-046a**: The system MUST create and update run records before and after each SfM substage so interrupted runs remain auditable and resumable.
- **FR-046b**: The system MUST infer prior SfM stage state from filesystem outputs when canonical run records are missing or incomplete.
- **FR-047**: Public example configs and public generated documentation MUST NOT contain private dataset paths, credentials, or machine-specific absolute paths.
- **FR-048**: This feature MUST NOT run splat outlier filtering, patch generation, LFS training, cleanup, SOG compression, splat merging, NanoGS, LOD, PlayCanvas packaging, or mega-patching.

### Key Entities *(include if feature involves data)*

- **SfM Run**: The COLMAP portion of a pipeline attempt, including validation, intrinsics handling, feature extraction, matching, reconstruction, undistortion, optional dense output, optional mesh output, timing records, logs, and status.
- **Image Collection**: The raw project images organised as either a single-camera folder or camera-specific folders under the project image input.
- **Camera Group**: A logical camera source inferred from image layout or explicit user mapping, with image count, dimensions, metadata consistency status, and camera model handling.
- **Recoloured Image Collection**: Optional image collection with the same relative layout and filenames as the raw images, used only for undistorted downstream splatting inputs.
- **Intrinsics Source**: The selected source of camera intrinsics for reconstruction: default pre-calculation, user-supplied camera file, or explicit refinement setting.
- **Matching Strategy**: The selected image-pairing approach or named sequence of approaches used before reconstruction.
- **Vocabulary Tree Resource**: A configured local resource required by matching modes that perform vocabulary-tree retrieval.
- **Sparse Reconstruction Output**: The raw-image sparse model produced by SfM before undistortion.
- **Selected Sparse Model**: The sparse reconstruction model chosen for undistortion and downstream stages when one or more sparse models are produced.
- **Undistorted SfM Output**: The undistorted images and undistorted sparse model, including the intrinsics that downstream splatting stages must use.
- **Dense/Mesh Output**: Optional comparison artefacts produced only when explicitly enabled.
- **SfM Stage Decision**: A recorded up-front choice to resume, reuse, rerun, or overwrite prior outputs for one or more SfM stages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a valid small single-camera or multi-camera project, a researcher can complete the SfM stages and identify the sparse output, undistorted image output, undistorted sparse output, timings, and command log from the run record.
- **SC-002**: 100% of invalid image layouts, mixed per-camera image dimensions, invalid user camera files, unsupported reconstruction backends, and missing recoloured counterparts are rejected before feature extraction begins.
- **SC-003**: For every SfM run, the researcher can determine which image source was used for sparse reconstruction and which image source was used for undistortion.
- **SC-004**: For every successful SfM run, timings are available for each SfM stage that ran, including each matching pass.
- **SC-005**: For a run with prior partial or completed SfM outputs, all required resume/reuse/rerun/overwrite decisions are completed before the first requested SfM stage starts.
- **SC-006**: Dense and mesh stages remain skipped in default runs and run only when explicitly enabled.
- **SC-007**: Public examples and docs can be reviewed without exposing private local paths or credentials.

## Assumptions

- Feature 1 already provides the primary CLI entrypoint, config loading, project path derivation, CLI overrides, run records, external tool validation, and resume-policy foundations.
- The researcher is running on a Linux workstation prepared for COLMAP `4.0.4`.
- Raw image inputs are never modified in place.
- Underwater reef datasets should not rely on EXIF GPS or pose data by default.
- Recoloured images are optional and are intended for later appearance-sensitive splatting outputs, not for raw-image SfM.
- The default matching strategy is intended for sequence-based, loop-heavy reef captures, often with two cameras.
- Dense and mesh outputs are research comparison artefacts, not prerequisites for later splatting stages.
- Legacy standalone GLOMAP, NanoGS, LOD, PlayCanvas packaging, mega-patching, and all splatting stages are outside this feature.
