# Feature Specification: Camera Selection V3

**Feature Branch**: `009-camera-selection-v3`  
**Created**: 2026-06-18  
**Status**: Draft  
**Input**: User description: "Improve patch camera selection for SfM-derived Gaussian splat training by keeping useful internal cameras first and adding only capped neighbouring external support."

## Clarifications

### Session 2026-06-18

- Q: What should happen if useful internal cameras exceed the final `max_cameras` cap? → A: This cannot happen because patch bounds are generated to fit within `max_cameras`; treat it as a patch-bound generation defect, not a normal selection case.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preserve Useful Internal Patch Cameras (Priority: P1)

A reef reconstruction researcher can generate patch camera selections where cameras inside a patch that provide useful evidence for that patch are kept for training instead of being displaced by external support views.

**Why this priority**: The known failed selections dropped useful internal camera strips and bend views, which directly damages patch splat training quality.

**Independent Test**: Can be tested on diagnostic-only patch generation for Dataset 1 at 400 cameras, confirming that the p002 strip case and p007 bend case retain useful internal cameras before any splat training is run.

**Acceptance Scenarios**:

1. **Given** an SfM reconstruction and a patch with cameras whose centres fall inside the patch footprint, **When** camera selection runs, **Then** every internal camera with enough target image share and either patch-track evidence or patch-footprint evidence is kept.
2. **Given** a useful internal camera and useful external support cameras compete for the same final camera cap, **When** the final patch camera set is selected, **Then** the useful internal camera is kept and external support is limited to remaining capped capacity.
3. **Given** an internal camera only sees a sliver of the target patch, **When** its target image share is below the configured minimum, **Then** it is rejected rather than kept as useful internal evidence.

---

### User Story 2 - Add Only Capped Neighbouring External Support (Priority: P1)

A researcher can add oblique neighbouring support views to a patch without allowing those support views to replace useful internal cameras or come from unrelated distant patches.

**Why this priority**: External support can improve splat training around patch boundaries, but the V2 failure showed that uncapped or over-promoted external support harms core patch coverage.

**Independent Test**: Can be tested by sweeping the external support fraction on Dataset 1 and Dataset 2 diagnostic runs, confirming external counts remain within allowance and all selected external cameras come from one-ring neighbouring patches.

**Acceptance Scenarios**:

1. **Given** external support is enabled, **When** neighbouring external cameras are considered, **Then** only cameras belonging to one-ring neighbouring patches are eligible.
2. **Given** a non-neighbouring camera has strong apparent coverage, **When** camera selection runs, **Then** it is excluded from the selected set.
3. **Given** the configured external support fraction is zero, **When** camera selection runs, **Then** the selected set contains only useful internal cameras.
4. **Given** external support is enabled and useful neighbouring candidates exist, **When** support cameras are ranked, **Then** selected support balances patch evidence with view-angle diversity around the patch.

---

### User Story 3 - Size Patch Bounds For Internal Cameras (Priority: P2)

A researcher can create patch bounds sized for the intended internal-camera body of the patch while reserving only a small, explicit part of the final cap for external support.

**Why this priority**: If patch bounds are created against the final cap, external support capacity distorts the patch body and repeats the failure mode where support views crowd out internal views.

**Independent Test**: Can be tested by generating patch metadata with `max_cameras: 400` and `external_support_fraction: 0.10`, confirming patch-bound creation targets 360 internal cameras while the final camera cap remains 400.

**Acceptance Scenarios**:

1. **Given** a maximum camera cap and an external support fraction, **When** patch bounds are generated, **Then** the patch body is sized using the internal camera target rather than the final cap.
2. **Given** patch bounds are written, **When** diagnostics and downstream patching read patch metadata, **Then** they use the canonical nested bounds as the complete patch footprint, including buffer.
3. **Given** the number of useful internal cameras exceeds the internal target, **When** the final camera set is selected, **Then** the system keeps those useful internal cameras within the final cap and reports a warning.

---

### User Story 4 - Inspect Camera Selection Decisions Before Training (Priority: P2)

A researcher can run diagnostics only, inspect per-patch plots and CSVs, compare known bad cases against V3 selections, and decide whether to proceed to splat training.

**Why this priority**: Patch training is expensive. The project needs cheap, visual evidence that camera selection is sane before launching LichtFeld Studio runs.

**Independent Test**: Can be tested by producing the requested PNG-only sweep folders, summary CSV, review notes, and side-by-side outputs for Dataset 1 p002 and p007 without launching splat training.

**Acceptance Scenarios**:

1. **Given** diagnostics-only validation is requested, **When** camera selection runs on Dataset 1 and Dataset 2, **Then** it creates per-patch PNGs for each requested support fraction plus a run-level summary and review notes.
2. **Given** a known bad V2 case, **When** comparison output is generated, **Then** V3 support-fraction folders contain the camera-selection image, coverage CSV, patch metadata, and summary needed for review.
3. **Given** per-patch diagnostics are written, **When** a researcher opens them, **Then** kept internal, rejected internal, selected external, and unused external cameras are visually distinguishable.

### Edge Cases

- `external_support_fraction` is `0`, so all external support is disabled and only useful internal cameras can be selected.
- `external_support_fraction` would reserve more support cameras than remaining capacity after useful internal cameras are kept.
- Useful internal camera count exceeds the internal patch target while still fitting within the final camera cap.
- Useful internal camera count exceeds the final camera cap, indicating patch-bound generation failed to preserve the V3 sizing invariant.
- Selected camera count reaches the final maximum camera cap.
- A camera's projected patch target has fewer than three usable vertices and must be treated as having no patch footprint or image-share evidence.
- Sparse points are used for patch-track evidence only; they are not used to draw or approximate the camera footprint or target image area.
- A patch has footprint coverage below `0.25` or selected cameras with target image share within `0.01` of the `0.05` minimum threshold.
- A neighbouring external camera has no patch-track evidence and no patch-footprint evidence.
- A non-neighbouring camera appears useful but is outside the allowed one-ring support set.
- Patch metadata is missing canonical nested bounds.
- Diagnostic plots or CSVs cannot be written even though the selected camera set is valid.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose `advanced.splat.patching.external_support_fraction` as the only swept V3 camera-selection parameter, defaulting to `0.10`.
- **FR-002**: The system MUST keep the existing final camera cap setting as the hard maximum number of selected cameras per patch.
- **FR-003**: The system MUST derive an external support allowance from the final camera cap and external support fraction, then derive an internal camera target from the remaining capacity.
- **FR-004**: The system MUST use the internal camera target, not the final camera cap, when creating patch bounds, while preserving the invariant that useful internal cameras fit within the final camera cap.
- **FR-005**: The system MUST store canonical nested patch bounds and treat those bounds, including buffer, as the full patch footprint for camera selection and diagnostics.
- **FR-006**: The system MUST classify internal cameras by camera-centre inclusion inside the patch footprint when projected to the scene plane.
- **FR-007**: The system MUST score camera usefulness using exactly these evidence categories: patch COLMAP tracks seen, patch/frustum footprint overlap, and target image share.
- **FR-007a**: The system MUST compute patch/frustum footprint overlap from the raw rectangular patch footprint intersected with each candidate camera's frustum footprint on an XY-parallel plane at the patch's median sparse-point Z, not from sparse-point hulls, sparse-point bounding boxes, or sparse-point density.
- **FR-007b**: The system MUST compute target image share by projecting the patch/frustum intersection polygon into the candidate image and measuring the projected polygon area relative to image area.
- **FR-008**: The system MUST NOT use a special edge, boundary, buffer, or sparse-density score for V3 camera usefulness.
- **FR-009**: The system MUST keep every useful internal camera and MUST NOT thin useful internal cameras to make room for external support.
- **FR-010**: The system MUST reject internal cameras that fail the minimum target image share or have neither patch-track evidence nor patch-footprint evidence.
- **FR-011**: The system MUST consider external support cameras only from one-ring neighbouring patches.
- **FR-012**: The system MUST exclude non-neighbouring external cameras even when they have good apparent evidence.
- **FR-013**: The system MUST rank useful neighbouring external support using patch evidence and view-angle diversity.
- **FR-014**: The system MUST add external support only after useful internal cameras have been selected.
- **FR-015**: The system MUST cap selected external support by both the configured external support allowance and the remaining final camera capacity.
- **FR-016**: The system MUST select no external support when `external_support_fraction` is `0`.
- **FR-017**: The system MUST never exceed the configured final camera cap.
- **FR-018**: The system MUST record warnings when useful internal count exceeds the internal target, selected count reaches the final cap, patch-level footprint coverage is below `0.25`, or any selected camera has target image share within `0.01` of the minimum threshold.
- **FR-018a**: The system MUST treat useful internal camera count exceeding the final camera cap as a patch-bound generation defect rather than a normal external-support selection case.
- **FR-019**: The system MUST keep the existing diagnostic filenames `camera_coverage.csv`, `plot.png`, `plot.html`, `histogram.png`, and `generation.log`.
- **FR-020**: The system MUST record per-patch counts for selected internal, rejected internal, selected external, and unused external cameras.
- **FR-021**: The system MUST record per-patch camera-selection settings, target image share summaries, footprint overlap summaries, selected camera track summaries, and warnings.
- **FR-022**: The system MUST make diagnostics visually distinguish kept internal, rejected internal, selected external, and unused external cameras.
- **FR-023**: The system MUST support diagnostics-only validation before splat training, and the first V3 validation pass MUST NOT invoke LichtFeld Studio or patch splat training until diagnostics are reviewed.
- **FR-024**: The system MUST produce PNG-only sweep folders for Dataset 1 and Dataset 2 at support fractions `0.05`, `0.10`, and `0.15` for 400-camera diagnostics.
- **FR-025**: The system MUST produce side-by-side comparison artefacts for the known Dataset 1 p002 and p007 bad cases.
- **FR-027**: The system MUST keep public specs, configs, examples, and diagnostics instructions free of private local paths.

### Key Entities *(include if feature involves data)*

- **Patch Footprint**: The canonical rectangular patch area from nested patch bounds, including buffer, used for internal-camera classification and camera/patch overlap decisions.
- **Internal Camera**: A camera whose centre falls inside the patch footprint when projected to the scene plane.
- **Neighbouring External Camera**: A camera outside the patch footprint that belongs to a one-ring neighbouring patch and may be used only as capped support.
- **Camera Evidence Record**: The per-camera evidence used for selection, including patch-track count from COLMAP sparse tracks, rectangle/frustum footprint overlap, projected target image share, usefulness decision, source class, and final selection state.
- **External Support Allowance**: The maximum number of selected external cameras reserved from the final camera cap by the external support fraction.
- **Camera Selection Diagnostic**: Per-patch human-inspectable outputs that explain counts, scores, warnings, and visual camera categories for review before training.
- **Validation Sweep Output**: The PNG-only dataset sweep, summary CSV, review notes, and known-bad-case comparison outputs used to approve V3 before splat training.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dataset 1 p002 at 400 cameras keeps useful internal camera strips in V3 diagnostic outputs for every swept external support fraction.
- **SC-002**: Dataset 1 p007 at 400 cameras keeps useful internal cameras around the bend in V3 diagnostic outputs for every swept external support fraction.
- **SC-003**: In all validation sweeps, selected external support count is less than or equal to the configured external support allowance for 100 percent of patches.
- **SC-004**: In all validation sweeps, 100 percent of selected external cameras come from one-ring neighbouring patches.
- **SC-005**: With `external_support_fraction: 0`, 100 percent of selected cameras are useful internal cameras.
- **SC-006**: Polish Town validation for the first 20 patches at 200 cameras includes useful neighbouring oblique support when support is enabled and excludes non-neighbour support.
- **SC-007**: Every generated validation patch includes `camera_coverage.csv`, `plot.png`, `plot.html`, `histogram.png`, `generation.log`, and patch metadata sufficient to audit the selection.
- **SC-008**: The V3 diagnostic sweep produces all six requested Dataset 1 and Dataset 2 PNG folders, plus one `summary.csv` and one `review_notes.md`.
- **SC-009**: The known bad Dataset 1 p002 and p007 comparison folders each contain V2 bad evidence and V3 outputs for support fractions `0.05`, `0.10`, and `0.15`.

## Assumptions

- Feature 3 patching, run records, config loading, and diagnostics infrastructure already exist.
- COLMAP SfM outputs provide camera poses, intrinsics, sparse points, image observations, and image dimensions needed for camera evidence.
- Sparse points and image observations are used for track counts. Sparse point Z values set a single representative patch projection plane; rectangle/frustum geometry, not sparse-point shape, is used for footprint overlap and target image share.
- Wildflow remains the only patch-bound generator for this feature.
- `min_target_image_share` remains fixed at `0.05` for the first V3 validation run.
- Only `external_support_fraction` is swept during first validation; all other camera-selection thresholds and weights remain fixed.
- Dataset 1, Dataset 2, the small test dataset, and the Polish Town diagnostic example are available locally for validation.
- V2 artefacts are comparison evidence only and are not an implementation source of truth.
