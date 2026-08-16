# Feature Specification: Dataset-Specific Undistorted Colour Profiles

**Feature Branch**: `012-colour-profiles-undistorted`
**Created**: 2026-07-22
**Status**: Approved
**Input**: Save dataset-specific GUI colour profiles and apply them only to undistorted training and evaluation images, including unattended Nebius runs, without changing off mode.

## User Scenarios & Testing

### User Story 1 - Safe undistorted colour training (Priority: P1)

A researcher enables colour restoration and trains splats from colour-corrected copies of the matching undistorted images while SfM and its outputs remain unchanged.

**Why this priority**: Training distorted pixels with undistorted geometry is scientifically invalid.

**Independent Test**: Run patch preparation with correction enabled and prove every selected image is a corrected copy of the matching undistorted image with unchanged dimensions and name.

**Acceptance Scenarios**:

1. **Given** completed SfM and a valid dataset profile, **When** splat training is requested, **Then** correction is applied to the consumed undistorted workspace and its matching sparse geometry is reused unchanged.
2. **Given** mode is off, **When** any existing SfM, splat, evaluation, or Nebius workflow runs, **Then** no profile, GUI, colour state, or corrected output is required or created.
3. **Given** full-resolution evaluation is requested with correction enabled, **When** evaluation starts, **Then** its full-resolution targets are corrected with the same profile.

---

### User Story 2 - Save and reuse one dataset's GUI edits (Priority: P2)

A researcher edits evenly selected global or per-camera keyframes in the existing GUI and atomically saves a portable profile for the same dataset.

**Why this priority**: Local visual editing must be reusable on a headless worker.

**Independent Test**: Export a profile, reload it without a GUI, and reproduce the same interpolated parameters for every image identity.

**Acceptance Scenarios**:

1. **Given** saved GUI keyframes, **When** a profile is exported, **Then** it contains relative dataset identities, complete parameters, ordering, interpolation, version, and no absolute paths or run state.
2. **Given** a profile and a different dataset identity/order, **When** application is requested, **Then** it fails before writing images.

---

### User Story 3 - Headless Nebius application (Priority: P3)

A researcher supplies a profile URI for an existing reusable SfM source and runs training/evaluation without a GUI.

**Why this priority**: Expensive training runs on headless infrastructure after local visual tuning.

**Independent Test**: Run the worker with a local test URI and verify provenance plus corrected training and evaluation workspaces.

**Acceptance Scenarios**:

1. **Given** profile mode and a valid profile path, **When** a non-interactive run starts, **Then** no GUI opens and profile provenance is recorded.
2. **Given** COLMAP-safe staged names, **When** the source is prepared, **Then** an explicit original-to-staged mapping resolves profile identities exactly.

### Edge Cases

- Corrupt, unsupported, cross-dataset, incomplete, or changed profiles fail before output publication.
- Partial corrected trees are never reused as complete.
- Legacy project-level recoloured images are never selected for splatting.
- Legacy staged sources are accepted only when their deterministic mapping reconstructs and verifies exactly.
- A valid undistorted workspace may contain only the SfM-registered subset of
  the profile's ordered images. Every consumed name must still resolve exactly;
  images rejected by SfM do not invalidate the profile.
- Profile changes require explicit overwrite; raw and undistorted SfM artefacts are never modified.

## Requirements

### Functional Requirements

- **FR-001**: Configuration MUST support exactly `off`, `gray_world`, `manual`, and `profile` colour modes.
- **FR-002**: `profile` MUST require a profile path, MUST be non-interactive, and other modes MUST reject a profile path.
- **FR-003**: `off` MUST retain its current no-op behaviour across local and remote workflows.
- **FR-004**: SfM and COLMAP undistortion MUST always consume raw images.
- **FR-005**: Splat training and evaluation MUST always consume images matching their undistorted sparse workspace.
- **FR-006**: Enabled correction MUST write validated run-local copies of only the consumed undistorted workspaces.
- **FR-007**: Training and evaluation MUST use the same colour domain when correction is enabled.
- **FR-008**: Users MUST be able to save the existing GUI's global or per-camera edited keyframes as an atomic, versioned, dataset-specific profile.
- **FR-009**: Profiles MUST contain no absolute paths, run lifecycle state, or credentials.
- **FR-010**: Application MUST validate dataset identity and require every
  consumed undistorted image to be an exact member of the profile's ordered
  image mapping before writing output.
- **FR-011**: SfM staging MUST persist an exact original-to-staged image mapping and reusable source bundles MUST retain it.
- **FR-012**: Corrected output reuse MUST require matching profile hash, workspace inventory, complete validation, and explicit overwrite for incompatible outputs.
- **FR-013**: Schema-v1 state and project-level recoloured images MUST be treated as legacy review artefacts and never splat inputs.
- **FR-014**: Nebius workers MUST optionally download a profile, verify recorded provenance, apply it headlessly, and upload application records.

### Key Entities

- **Colour Profile**: Versioned dataset identity, ordered images, keyframes, parameters, and interpolation settings.
- **Image Mapping**: Exact relationship between original dataset paths and COLMAP staged/undistorted names.
- **Corrected Workspace**: Atomic run-local RGB image tree paired with one unchanged undistorted sparse workspace.
- **Application Manifest**: Profile hash, source inventory, output validation, timings, and provenance.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of corrected training and evaluation images match their sparse model names and source dimensions.
- **SC-002**: 100% of maintained off-mode tests produce no colour workflow artefacts and retain existing sources.
- **SC-003**: A locally saved profile can be applied to its matching headless dataset with zero GUI interaction.
- **SC-004**: Dataset/profile mismatches and incomplete outputs fail before any final corrected tree is published.
- **SC-005**: Raw images and all SfM workspaces remain byte-for-byte unmodified by colour application.

## Assumptions

- Profiles are dataset-specific; cross-dataset interpolation is out of scope.
- Existing evenly spaced keyframe selection and linear interpolation remain authoritative.
- Only workspaces consumed by training or evaluation are corrected.
- Existing Pillow and NumPy processing is sufficient; no dependency is added.
