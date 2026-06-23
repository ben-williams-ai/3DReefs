# Feature Specification: Colour Restoration Modes

**Feature Branch**: `011-colour-restoration-modes`  
**Created**: 2026-06-23  
**Status**: Draft  
**Input**: User description: "Replace project.recolour_images with a top-level colour restoration configuration block. The block selects off, gray_world, or manual colour restoration, controls whether existing restored images are reused or overwritten, and owns the start-SfM-immediately behaviour. The rename is breaking; legacy configs must fail clearly. SfM and COLMAP undistortion must always use raw images. Off bypasses colour restoration, gray_world applies automatic full-resolution restoration without opening the GUI, and manual preserves the current GUI/keyframe workflow. Colour-restored images are only for splatting-stage image inputs and review."

## Clarifications

### Session 2026-06-23

- Q: How should reuse versus regeneration be configured when restored colour images already exist? → A: Add a top-level `colour_restoration` config block with `overwrite: false` by default, so existing restored images for the run are reused unless overwrite is explicitly enabled.
- Q: Should the top-level `colour_restoration` block itself be required, or may it be omitted entirely and default to off? → A: The `colour_restoration` block is required; if its mode is omitted, mode defaults to `off`.
- Q: Should `overwrite` apply to manual mode as well as `gray_world`, or only to automatic gray-world restoration? → A: `overwrite` applies to both `gray_world` and `manual` restored image outputs for the same run.
- Q: Should the mode field inside the top-level block be named `colour_restoration`, or should it be renamed to avoid the doubled path? → A: Use `colour_restoration.mode` for `off`, `gray_world`, or `manual`.
- Q: What pipeline stages may consume colour-restored images? → A: SfM and COLMAP undistortion always use raw images; colour-restored images are only for splatting-stage image inputs and review.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose Colour Restoration Explicitly (Priority: P1)

As a pipeline operator, I need every project configuration to expose a dedicated colour restoration section that states whether colour restoration is disabled, automatic, or manual so downstream splatting never guesses whether raw or colour-restored images should be used.

**Why this priority**: The previous boolean setting cannot express the three required behaviours and can lead to ambiguous handoffs between image preparation and splat stages, while SfM must remain raw-image-only.

**Independent Test**: Load project configurations for each allowed mode in the required top-level colour restoration block and verify that each mode is accepted, omitted mode defaults to off, documented examples load successfully, invalid modes are rejected, missing colour restoration blocks are rejected, and legacy `project.recolour_images` configurations fail with an explicit migration error.

**Acceptance Scenarios**:

1. **Given** a top-level colour restoration block with `mode: off`, **When** the configuration is validated, **Then** validation succeeds and the project is identified as using raw images.
2. **Given** a top-level colour restoration block with `mode: gray_world`, **When** the configuration is validated, **Then** validation succeeds and the project is identified as requiring automatic colour restoration.
3. **Given** a top-level colour restoration block with `mode: manual`, **When** the configuration is validated, **Then** validation succeeds and the project is identified as requiring the manual colour workflow.
4. **Given** a colour restoration block without a mode value, **When** the configuration is validated, **Then** validation succeeds and defaults to using raw images.
5. **Given** a project configuration without the top-level colour restoration block, **When** the configuration is validated, **Then** validation fails with a clear message explaining that the block is required.
6. **Given** a project configuration that still uses `project.recolour_images`, **When** the configuration is validated, **Then** validation fails with a clear message explaining that the top-level colour restoration block is required instead.

---

### User Story 2 - Run Without Colour Restoration (Priority: P2)

As a pipeline operator processing images that do not need correction, I need to turn colour restoration off so that splatting uses the raw image set and no colour workflow state is created or opened.

**Why this priority**: Some datasets should pass through unchanged, and disabling the workflow must be predictable rather than relying on skipped prompts or previously generated files.

**Independent Test**: Run the pipeline with colour restoration off and verify that it does not create or open colour state, does not create recoloured outputs, SfM uses raw images, and splatting remains on the normal raw-image path.

**Acceptance Scenarios**:

1. **Given** a valid project configured with colour restoration mode `off`, **When** SfM and splatting preparation run, **Then** raw images are used and no colour state or restoration application step is started.
2. **Given** existing recoloured outputs from a previous run, **When** a project is configured with colour restoration mode `off`, **Then** those outputs are not silently used as the SfM, undistortion, or splatting image source.

---

### User Story 3 - Run Automatic Gray-World Restoration (Priority: P2)

As a pipeline operator who wants a consistent automatic correction, I need gray-world restoration to generate a complete recoloured image tree without launching the manual interface, then use those images only for splatting-stage image inputs after raw-image SfM is complete.

**Why this priority**: Automatic restoration should support unattended processing while preserving raw-image SfM geometry and producing explicit, complete outputs for splatting.

**Independent Test**: Run restoration with colour restoration mode `gray_world` and verify that all dataset images are restored at full resolution, dimensions and colour channels are preserved, completion is recorded, no GUI opens, SfM and COLMAP undistortion still use raw images, and splatting uses the restored image set. Repeat with existing same-run restored images and verify that `overwrite: false` reuses them while `overwrite: true` regenerates them.

**Acceptance Scenarios**:

1. **Given** a valid project configured with colour restoration mode `gray_world`, **When** colour preparation runs, **Then** every dataset image receives gray-world correction at full strength and is written to the recoloured output tree.
2. **Given** automatic restoration completes successfully, **When** SfM and COLMAP undistortion run, **Then** they use raw images and never the completed recoloured image tree.
3. **Given** automatic restoration completes successfully, **When** splatting image inputs are prepared, **Then** the completed recoloured image tree is used for splatting images while raw-image SfM geometry remains unchanged.
4. **Given** automatic restoration is requested from a colour apply command or full pipeline route, **When** the command runs, **Then** it completes without opening the manual colour interface.
5. **Given** existing restored colour images for the same run and `overwrite: false`, **When** automatic restoration is requested, **Then** the existing restored images are reused.
6. **Given** existing restored colour images for the same run and `overwrite: true`, **When** automatic restoration is requested, **Then** the restored images are regenerated through an explicit overwrite path.

---

### User Story 4 - Continue Manual Colour Workflow (Priority: P3)

As a user performing visual colour correction, I need the existing manual keyframe workflow to continue working when the mode is `manual`, including resume, completion, and blocking safeguards before dependent processing.

**Why this priority**: Manual correction remains necessary for datasets where automatic correction is insufficient, and existing workflow guarantees must remain intact.

**Independent Test**: Run manual mode through open, resume, apply, and downstream preflight paths and verify that the manual interface, corrected output reuse, completion state, and active-session blocking behave as before.

**Acceptance Scenarios**:

1. **Given** a project configured with colour restoration mode `manual`, **When** the user opens the colour workflow, **Then** the manual interface opens or resumes the existing session.
2. **Given** manual restoration is active and incomplete, **When** a dependent splat stage that would use colour-restored images is requested, **Then** the request is blocked with a clear instruction to finish or resolve the manual workflow first.
3. **Given** manual restoration has completed, outputs are still valid for that manual run, and `overwrite: false`, **When** splatting-stage processing resumes, **Then** those corrected outputs may be reused where reuse is explicitly safe.
4. **Given** manual restoration has completed, outputs are still valid for that manual run, and `overwrite: true`, **When** manual restoration is requested again, **Then** the corrected outputs are regenerated through an explicit overwrite path.

### Edge Cases

- Legacy configurations containing `project.recolour_images` must fail rather than being interpreted as any new mode.
- Legacy configurations containing `project.start_sfm_immediately` must fail rather than being interpreted as the new colour restoration workflow setting.
- Configurations without the top-level colour restoration block must fail clearly.
- Configurations with misspelled, differently cased, or unsupported colour restoration values must fail clearly.
- Configurations without an explicit colour restoration mode must default to off.
- Existing recoloured outputs from another mode or stale run must not be treated as valid fallback inputs.
- Existing restored images for the same run must be reused when `overwrite: false` and regenerated only when `overwrite: true`, regardless of whether they were produced by `gray_world` or `manual`.
- Automatic restoration must not silently produce a partial recoloured image set; incomplete outputs must be reported as a failure or require an explicit regeneration path.
- SfM feature extraction, matching, reconstruction, and COLMAP undistortion must always use raw images, regardless of colour restoration mode or completion state.
- Colour-restored images must be considered valid only for splatting-stage image inputs and user review, never for SfM or COLMAP undistortion.
- Manual-mode active or incomplete state must block only splatting workflows that need colour-restored image inputs; `off` and completed `gray_world` runs must not be blocked by manual-specific checks.
- User-facing commands that open the colour interface must explain that opening is meaningful only for manual restoration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Project configuration MUST provide a top-level `colour_restoration` block for colour workflow settings and MUST reject configurations where the block is absent.
- **FR-002**: The top-level colour restoration block MUST support a `mode` setting with exactly one of these values: `off`, `gray_world`, or `manual`, defaulting to `off` when the block does not specify a mode.
- **FR-003**: The top-level colour restoration block MUST support an `overwrite` setting, defaulting to `false`, that controls whether existing restored colour images for the same run are reused or regenerated for both automatic and manual restoration modes.
- **FR-004**: The top-level colour restoration block MUST support `start_sfm_immediately`, defaulting to `true`, for the manual workflow's background raw-image SfM behaviour.
- **FR-005**: Project configuration MUST reject legacy `project.recolour_images` settings with a clear validation error that names the replacement top-level colour restoration block.
- **FR-006**: Project configuration MUST reject legacy `project.start_sfm_immediately` settings with a clear validation error that names the replacement top-level colour restoration block.
- **FR-007**: Project configuration MUST reject unsupported colour restoration mode values with a clear validation error.
- **FR-008**: All maintained example, dataset, test, contract, and generated configurations MUST use the top-level colour restoration block and omit `project.recolour_images`.
- **FR-009**: Documentation and example configuration comments MUST describe `off` as skipping colour restoration and using raw images.
- **FR-010**: Documentation and example configuration comments MUST describe `gray_world` as applying gray-world correction at full strength to every dataset image without opening the manual interface.
- **FR-011**: Documentation and example configuration comments MUST describe `manual` as using the existing GUI and keyframe workflow.
- **FR-012**: Documentation and example configuration comments MUST describe `overwrite: false` as reusing existing restored images for the same run and `overwrite: true` as regenerating them for both `gray_world` and `manual` modes.
- **FR-013**: Documentation and example configuration comments MUST describe `start_sfm_immediately` as allowing raw-image SfM to start in the background while the manual colour restoration GUI is available for editing.
- **FR-014**: When colour restoration is `off`, the pipeline MUST bypass colour state, manual interface, and restoration application orchestration, then use raw images for SfM, COLMAP undistortion, and splatting.
- **FR-015**: The pipeline MUST always use raw images for SfM feature extraction, matching, reconstruction, and COLMAP undistortion, regardless of colour restoration mode.
- **FR-016**: The pipeline MUST use completed colour-restored images only for splatting-stage image inputs and user review, never for SfM or COLMAP undistortion.
- **FR-017**: When colour restoration is `gray_world`, the pipeline MUST produce a complete recoloured image tree for all dataset images before splatting uses restored images.
- **FR-018**: Gray-world restoration outputs MUST preserve the source images' dimensions and produce usable colour images for downstream splatting.
- **FR-019**: Gray-world restoration MUST record colour restoration as complete for the run and MUST NOT launch the manual interface.
- **FR-020**: When colour restoration is `manual`, the pipeline MUST preserve the existing manual open, resume, apply, completion, and splatting-stage blocking behaviour.
- **FR-021**: The system MUST NOT silently fall back between colour restoration modes or use existing recoloured outputs from an incompatible mode as valid splatting inputs.
- **FR-022**: Existing restored colour images for the same run MUST be reused when `overwrite` is `false`, for both `gray_world` and `manual` modes.
- **FR-023**: Existing restored colour images for the same run MUST be regenerated through an explicit overwrite path when `overwrite` is `true`, for both `gray_world` and `manual` modes.
- **FR-024**: Existing restored colour images from another run, another mode, or an incompatible state MUST NOT be treated as valid reusable splatting inputs.
- **FR-025**: Manual corrected output reuse MUST occur only where the system can explicitly determine that reuse is safe for manual-mode splatting outputs.
- **FR-026**: Commands and documentation MUST clarify that opening the colour interface is meaningful only for manual restoration.
- **FR-027**: Commands and documentation MUST clarify that gray-world restoration can be run through the colour apply route or the full pipeline without opening the manual interface.
- **FR-028**: Splat preflight checks MUST block on active or incomplete manual colour state only when splatting would consume colour-restored image inputs, and MUST NOT block solely because restoration is off or completed through gray-world restoration.

### Key Entities *(include if feature involves data)*

- **Project Configuration**: The configuration settings that determine which image preparation mode is used for the run. Key relationship: owns a top-level colour restoration block.
- **Colour Restoration Block**: The top-level configuration block for colour workflow behaviour. Key attributes: `mode`, `overwrite`, and `start_sfm_immediately`.
- **Colour Restoration Mode**: The selected behaviour for image colour handling. Allowed values are `off`, `gray_world`, and `manual`; the default is `off`.
- **Restored Image Set**: The complete set of images produced by a restoration mode for splatting-stage image inputs and user review; it is never an SfM or COLMAP undistortion source.
- **Colour Workflow State**: The run-level record of manual or automatic restoration progress and completion status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of maintained example, dataset, and test configurations validate successfully using the required top-level colour restoration block.
- **SC-002**: 100% of configurations using `project.recolour_images` or `project.start_sfm_immediately` fail validation with an error that identifies the top-level colour restoration block as the required replacement.
- **SC-003**: 100% of configurations omitting the top-level colour restoration block fail validation with an error that identifies the missing block.
- **SC-004**: In off mode, colour restoration creates zero new colour workflow state files or restored image outputs during SfM and splatting preparation.
- **SC-005**: In gray-world mode, restoration produces one restored output for every source dataset image, with matching dimensions for every output checked.
- **SC-006**: In every mode, SfM and COLMAP undistortion use raw images in 100% of covered tests.
- **SC-007**: In manual mode, existing manual workflow regression tests for open, resume, apply, completion, reuse, and active-session blocking continue to pass.
- **SC-008**: Splat preflight outcomes match the selected mode in all covered tests: no manual-state block for off mode, no manual-state block for completed gray-world mode, and a clear block for active or incomplete manual mode.
- **SC-009**: For same-run restored images in both `gray_world` and `manual` modes, tests demonstrate that `overwrite: false` reuses existing outputs and `overwrite: true` regenerates them.
- **SC-010**: In gray-world and completed manual modes, splatting-stage image input tests demonstrate that colour-restored images are used only after compatible completed colour state exists.

## Assumptions

- This is a breaking configuration migration with no compatibility alias for `project.recolour_images`.
- `start_sfm_immediately` moves into the top-level colour restoration block and only affects the manual restoration workflow.
- Existing image outputs are user data and must not be silently deleted; replacement requires an explicit overwrite or regeneration decision.
- The existing manual GUI/keyframe workflow remains the expected user experience for manual restoration.
- Existing restored outputs are not portable across modes unless the system has an explicit, mode-aware validation and reuse path.
