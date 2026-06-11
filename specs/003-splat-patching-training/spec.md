# Feature Specification: Splat Patching And Training

**Feature Branch**: `003-splat-patching-training`  
**Created**: 2026-06-11  
**Status**: Draft  
**Input**: User description: "Create Feature 3: Splat Patching And Training for 3DReefs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Trainable Reef Patches (Priority: P1)

A researcher with a completed COLMAP SfM run can create inspectable patch datasets for Gaussian splatting. Each patch has a bounded region, a selected image set, the sparse reconstruction needed for training, and diagnostics that explain which cameras were assigned and why.

**Why this priority**: Patch creation is the bridge between SfM and splatting. If patches are wrong, all later training, cleanup, compression, and merging inherit the mistake.

**Independent Test**: Can be tested by running the patching stage on the completed test dataset SfM output and confirming that patch folders, patch metadata, selected images, sparse data, and diagnostics are produced without launching splat training.

**Acceptance Scenarios**:

1. **Given** a completed SfM run with undistorted images and sparse outputs, **When** the researcher runs the patching stage, **Then** the system creates one or more patch datasets with selected cameras, selected images, patch metadata, sparse reconstruction data, and diagnostics for each patch.
2. **Given** a patch size limit selected by the researcher, **When** patches are generated, **Then** each patch reports how many cameras were selected and whether it is within the configured limit.
3. **Given** camera poses and sparse points from a reef reconstruction, **When** patch regions are created, **Then** birds-eye regions are used only as spatial anchors and final camera assignment is based on view quality and coverage rather than simple camera centre inclusion alone.

---

### User Story 2 - Audit And Filter Camera Pose Outliers (Priority: P2)

A researcher can detect and remove obviously bad camera poses before patching, while keeping a clear record of what changed and why.

**Why this priority**: Large reef reconstructions can contain badly localised cameras that distort patch bounds and camera selection. Filtering must be auditable because it changes the reconstruction used for training.

**Independent Test**: Can be tested by running the outlier filtering stage on a valid SfM output and confirming that the stage records either "no outliers removed" or lists removed cameras with scores, thresholds, and before/after diagnostics.

**Acceptance Scenarios**:

1. **Given** a reconstruction with no detected camera outliers, **When** filtering runs, **Then** the system keeps all cameras and records that no outliers were removed.
2. **Given** a reconstruction with detected camera outliers, **When** filtering runs, **Then** the system writes a filtered copy for downstream patching and records which cameras were removed, the scores used, the threshold used, and before/after camera pose diagnostics.
3. **Given** the researcher requests a dry run, **When** outlier filtering runs, **Then** the system reports proposed removals without changing the downstream patching input.

---

### User Story 3 - Train Patch Splats In Batch (Priority: P3)

A researcher can train LichtFeld Studio splats for all generated patches, or for an explicit subset of patches, while receiving clear patch-level completion status.

**Why this priority**: Batch training is the main expensive work of this feature. The researcher needs unattended operation, but also enough status information to know which patches succeeded, partially completed, or failed.

**Independent Test**: Can be tested by running training on the test dataset patches with a small iteration override and confirming that each requested patch receives a status record, training logs, output artefact information, and completion warnings where appropriate.

**Acceptance Scenarios**:

1. **Given** generated patch datasets, **When** the researcher runs patch training, **Then** the system trains each requested patch and records requested iterations, completed iterations, completion ratio, output artefacts, return status, and duration.
2. **Given** the researcher supplies a patch list, **When** training runs, **Then** only those patches are trained and skipped patches are clearly recorded as not requested.
3. **Given** a patch training run finishes before the requested iteration count, **When** status is recorded, **Then** completion below 80 percent is flagged as severe and completion from 80 percent up to less than 100 percent is flagged as a warning.
4. **Given** automatic retraining is disabled by default, **When** a patch fails or under-completes, **Then** the system does not silently retrain it but makes the failure visible and allows an explicit retrain setting to be used later.

---

### User Story 4 - Resolve Existing Patch Outputs Up Front (Priority: P4)

A researcher can resume, overwrite, or skip existing patching and training outputs without being interrupted midway through a long run.

**Why this priority**: Patch generation and splat training are expensive. Existing outputs must be handled consistently with the project constitution so unattended runs do not pause halfway through.

**Independent Test**: Can be tested by creating partial patching or training outputs, rerunning the same requested stages, and confirming that all resume/overwrite decisions happen before any requested stage starts.

**Acceptance Scenarios**:

1. **Given** existing patch outputs are present, **When** the researcher starts patching, **Then** the system detects them during preflight and resolves whether to resume, overwrite, or stop before any patching work begins.
2. **Given** existing training outputs are present for one or more requested patches, **When** the researcher starts training, **Then** the system resolves each requested patch's existing-output decision before any training begins.
3. **Given** the effective config has changed since a partial run, **When** the researcher chooses to continue, **Then** the system warns clearly and records the changed settings with the run records.

### Edge Cases

- The requested SfM run has no undistorted sparse output, missing undistorted images, missing camera intrinsics, or sparse image names that do not match available undistorted image paths.
- The SfM output contains multiple camera folders or camera names, and patching must preserve the image layout needed for training.
- Camera pose outlier filtering would remove too many cameras or leave too few cameras for useful patching.
- Patch size settings are missing, zero, negative, or so restrictive that a useful patch cannot be created.
- A generated patch has no sparse points, no selected images, too few selected images, or selected images that cannot be found on disk.
- A view-based camera selection diagnostic cannot be written even though the patch sparse data is valid.
- The researcher requests a patch name that does not exist.
- Training is requested before patching has produced valid patch datasets.
- LichtFeld Studio is missing, cannot run in the required unattended mode, or exits with an error for one or more patches.
- A patch produces partial training output but no final-iteration output.
- A non-interactive run encounters a condition that would normally require a resume/overwrite prompt.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST validate completed SfM outputs required for splat patching before outlier filtering, patch generation, or training begins.
- **FR-002**: The system MUST use COLMAP undistorted images and undistorted sparse outputs as the source for patching and splat training.
- **FR-003**: The system MUST preserve raw input images and SfM outputs by writing filtered or patched derivatives rather than modifying the only source copy in place.
- **FR-004**: The system MUST provide camera pose outlier filtering enabled by default, with a clear record of removed cameras, scores, thresholds, and the downstream reconstruction used.
- **FR-005**: The system MUST support a dry-run mode for camera pose outlier filtering that reports proposed removals without changing downstream patching inputs.
- **FR-006**: The system MUST create patch regions from the reconstruction using birds-eye regions as spatial anchors and then assign cameras using view-based selection.
- **FR-007**: The system MUST NOT require or expose point-cloud downsampling as part of patch generation for this feature.
- **FR-008**: The system MUST describe patch buffer and patch geometry in relative scene coordinates, not as metric metres.
- **FR-009**: The system MUST expose a maximum-cameras-per-patch setting as a high-visibility user choice because it controls the trade-off between patch size, VRAM demand, training time, and patch count.
- **FR-010**: The system MUST default the patch buffer to `0.1` unless the researcher overrides it.
- **FR-011**: The system MUST NOT expose target-bin patching as a user option in this feature.
- **FR-012**: The system MUST write patch metadata for every generated patch, including patch identity, selected image count, selected camera count, source reconstruction, and relevant patch settings.
- **FR-013**: The system MUST provide selected image access for every patch while preserving the original undistorted image files.
- **FR-014**: The system MUST write patch diagnostics for every generated patch, including enough information for the researcher to inspect camera coverage and selection quality.
- **FR-015**: The system MUST treat patch sparse export failures as blocking errors for the affected run.
- **FR-016**: The system MUST allow non-critical diagnostic export failures to be logged while continuing when the patch dataset itself is valid.
- **FR-017**: The system MUST train all generated patches by default when training is requested.
- **FR-018**: The system MUST allow the researcher to train only an explicit list of patch IDs.
- **FR-019**: The system MUST default patch training to 30,000 requested iterations.
- **FR-020**: The system MUST default the per-patch splat cap to 1,500,000 splats.
- **FR-021**: The system MUST default patch training to unattended/headless operation.
- **FR-022**: The system MUST record status for every requested training patch, including requested iterations, completed iterations, completion ratio, output artefact, return status, and duration.
- **FR-023**: The system MUST flag training completion below 80 percent of requested iterations as severe.
- **FR-024**: The system MUST flag training completion from 80 percent up to less than 100 percent as a warning.
- **FR-025**: The system MUST NOT automatically retrain failed or incomplete patches unless the researcher explicitly enables retraining.
- **FR-026**: The system MUST support explicit retraining of missing, failed, or incomplete patch outputs.
- **FR-027**: The system MUST record patching and training timings through the existing run-record system.
- **FR-028**: The system MUST record patching logs, LFS logs, warnings, and patch-level status through the existing run-record system.
- **FR-029**: The system MUST detect existing patching and training outputs before running any requested stage and resolve resume, overwrite, skip, or stop decisions up front.
- **FR-030**: The system MUST warn when relevant config values differ from a previous partial patching or training run before continuing that run.
- **FR-031**: The system MUST fail clearly in non-interactive mode if a required existing-output decision has not been supplied.
- **FR-032**: The system MUST keep cleanup, SOG compression, final splat merging, NanoGS, LOD, PlayCanvas packaging, and mega-patching out of this feature.

### Key Entities *(include if feature involves data)*

- **Splat Source Reconstruction**: The validated undistorted SfM output used as the source for outlier filtering, patching, and training.
- **Camera Pose Outlier Record**: A record of a camera considered for removal, including its identity, score, threshold comparison, and filtering decision.
- **Filtered Reconstruction**: The reconstruction copy used for patching after outlier filtering has either kept all cameras or removed selected cameras.
- **Patch**: A trainable spatial subset of the reef reconstruction with a patch identity, bounds, selected cameras, selected images, sparse data, diagnostics, and training output location.
- **Patch Selection Diagnostic**: Human-inspectable evidence explaining how cameras were selected for a patch and whether coverage looks reasonable.
- **Patch Training Run**: The training attempt for one patch, including requested settings, completion status, output artefacts, warnings, and timing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the completed test dataset SfM output, the researcher can create valid patch datasets and inspect patch metadata and diagnostics for every patch before training.
- **SC-002**: On the completed test dataset SfM output, the researcher can run a short-iteration training smoke test for at least one patch and receive a patch-level status record showing requested iterations, completed iterations, completion ratio, output status, and duration.
- **SC-003**: Existing patching or training outputs are detected and resolved before any requested patching or training work starts in 100 percent of tested resume/overwrite scenarios.
- **SC-004**: Invalid inputs such as missing undistorted images, missing sparse outputs, missing selected images, impossible patch size settings, or unknown patch IDs fail before expensive training begins.
- **SC-005**: Every generated patch has auditable camera-selection information sufficient for the researcher to decide whether the patch should be trained, regenerated, or excluded.
- **SC-006**: Every requested training patch is classified as complete, warning, severe warning, failed, skipped, or not requested without requiring the researcher to parse terminal output.

## Assumptions

- Feature 1 run records, config loading, CLI overrides, tool validation, and resume/overwrite machinery are already available.
- Feature 2 has produced completed COLMAP undistorted images and undistorted sparse outputs.
- The first implementation will be validated on the existing small test dataset before attempting large reef datasets.
- The researcher will tune maximum cameras per patch for the available GPU and image dimensions; the system should make this trade-off visible but cannot perfectly predict VRAM use.
- Cleanup, SOG compression, and final merging will be handled by the next feature.
