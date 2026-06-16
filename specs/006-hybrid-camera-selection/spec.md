# Feature Specification: Hybrid Camera Selection

**Feature Branch**: `006-hybrid-camera-selection`  
**Created**: 2026-06-16  
**Status**: Draft  
**Input**: User description: "Create Feature 006: Hybrid Visibility Camera Selection for 3DReefs, replacing the current patch camera selector with the best approach found in scratch experiments."

## Clarifications

### Session 2026-06-16

- Q: When camera selection produces a patch with poor selector coverage, should that patch still train by default? → A: Create the patch, warn clearly, and still allow it to train by default.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select Robust Patch Cameras (Priority: P1)

A researcher generating splat patches receives a selected image set for each patch that covers the patch body, supports the patch boundary, avoids irrelevant outside content where possible, and stays within the configured maximum camera count.

**Why this priority**: Camera selection determines what each patch splat can learn. If patch body cameras are dropped, low-texture reef areas can become weak or hollow. If boundary support is poor, cleaned patch edges and merged outputs suffer.

**Independent Test**: Can be tested by running patch generation on completed reef SfM outputs and comparing camera-selection diagnostics against the current selector for known problematic patches without launching splat training.

**Acceptance Scenarios**:

1. **Given** a patch with low sparse-point density in part of the reef, **When** cameras are selected, **Then** the selected images still preserve broad acquisition coverage across the patch body rather than dropping an entire survey strip.
2. **Given** neighbouring cameras that genuinely see the patch target region, **When** cameras are selected, **Then** those neighbouring cameras can be included when they improve patch body or boundary coverage.
3. **Given** a local camera whose centre lies inside the patch but whose view does not cover the patch target region, **When** cameras are selected, **Then** that camera is not kept merely because it is local.
4. **Given** more useful candidate cameras than the configured camera limit, **When** selection completes, **Then** the selected image count does not exceed that limit.

---

### User Story 2 - Protect Boundaries Without Hollowing Interiors (Priority: P2)

A researcher can use boundary-support views for clean seams while preserving enough patch-body cameras to avoid hollowed or poorly covered interiors.

**Why this priority**: The old boundary-first selector helped oblique urban scenes but could allow support views to replace too many local body views in reef datasets. The new selector must keep the useful boundary behaviour without repeating the hollow-patch failure mode.

**Independent Test**: Can be tested by inspecting patch-selection plots and coverage summaries for Dataset 1 patch `p000`, Dataset 1 patch `p006`, and a Polish-town style oblique patch, confirming that selected cameras cover both patch body and edge regions.

**Acceptance Scenarios**:

1. **Given** a patch with many possible boundary support cameras, **When** cameras are selected, **Then** support views improve edge coverage without causing a large unrepresented gap in the patch body.
2. **Given** an oblique scene where neighbouring cameras see the patch edge or vertical structure better than local cameras, **When** cameras are selected, **Then** useful neighbouring views are kept even though they are not local.
3. **Given** candidate cameras that mostly see outside the patch target, **When** cameras are selected, **Then** those cameras are disadvantaged unless they add otherwise missing target coverage.

---

### User Story 3 - Audit Selection Decisions (Priority: P3)

A researcher can inspect why cameras were selected or rejected for each patch using diagnostics that expose coverage, local/nonlocal balance, spillover risk, and view diversity.

**Why this priority**: This feature changes a sensitive part of the pipeline. Researchers need enough evidence to decide whether patching is trustworthy before spending hours training splats.

**Independent Test**: Can be tested by running patch generation on a completed SfM run and confirming that every patch has human-readable diagnostics explaining selected and rejected camera groups.

**Acceptance Scenarios**:

1. **Given** patch camera selection completes, **When** the researcher opens the diagnostics, **Then** they can see selected local cameras, rejected local cameras, selected nonlocal/support cameras, unused support cameras, patch bounds, and neighbouring patch context.
2. **Given** a patch has low coverage, high spillover risk, or unusual nonlocal camera usage, **When** diagnostics are reviewed, **Then** the issue is visible without reading terminal output.
3. **Given** diagnostic plot generation fails but camera selection succeeds, **When** the patching stage finishes, **Then** the patch remains usable and the diagnostic failure is recorded as a warning.
4. **Given** a patch has poor selector coverage, **When** the patching stage finishes, **Then** the patch is still written and remains trainable by default, with clear warnings for the researcher to review.

---

### User Story 4 - Replace The Selector Without New User Complexity (Priority: P4)

A researcher continues using the existing patching workflow and camera-count setting, while the Target-Aware Spatial Greedy selector becomes the single supported selection behaviour.

**Why this priority**: The project should avoid maintaining multiple camera-selection modes and backwards-compatibility branches. The improved approach should replace the old selector cleanly once validated.

**Independent Test**: Can be tested by running the normal patch stage with existing configs and confirming that it uses the Target-Aware Spatial Greedy selector without requiring the researcher to choose between selector modes.

**Acceptance Scenarios**:

1. **Given** an existing config with patching enabled, **When** the patching stage runs, **Then** the Target-Aware Spatial Greedy selector is used by default without adding a selector-mode decision.
2. **Given** public example configs, **When** the researcher reviews patching settings, **Then** they see the existing high-level patch choices but no menu of legacy selector modes.
3. **Given** patching outputs from older selector experiments are present, **When** the researcher requests regeneration, **Then** overwrite or reuse decisions still happen up front before patching begins.

### Edge Cases

- A patch has few or no sparse points in part of the target region, but the image acquisition pattern suggests the area was photographed.
- A local camera is inside the patch footprint but primarily views outside the patch target.
- A neighbouring camera sees the patch target well and is more useful than a weak local camera.
- A neighbouring camera sees only a tiny sliver of the target region and mostly captures outside content.
- Dense textured coral, buildings, or other high-feature areas produce many sparse points that could dominate raw point-count selection.
- Candidate cameras provide highly redundant views from one direction.
- The configured maximum camera count is lower than the number of cameras needed for ideal coverage.
- A patch has too few usable target observations to make strong automatic selection decisions.
- A patch has poor selector coverage but is still needed for downstream inspection or training.
- Camera image names, patch metadata, or source sparse outputs are missing or inconsistent.
- Diagnostic artefacts cannot be written even though the selected patch dataset is otherwise valid.
- Existing patch outputs were generated by an older selector and patching is requested again.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST use the Target-Aware Spatial Greedy selector as the single supported patch camera-selection behaviour for splat patch generation.
- **FR-002**: The system MUST NOT expose legacy selector modes or a selector-mode choice in public configs for this feature.
- **FR-003**: The system MUST treat the stored patch bounds as the patch target region and MUST NOT expand the patch target a second time during camera selection.
- **FR-004**: The system MUST distinguish patch-body coverage from patch-boundary coverage when assessing candidate cameras.
- **FR-005**: The system MUST consider evidence that a camera actually observes the patch target region, including matched scene evidence where available and geometric target visibility where matched evidence is weak.
- **FR-006**: The system MUST allow local and nonlocal/support cameras to compete on target-region usefulness rather than choosing cameras solely by camera-centre location.
- **FR-007**: The system MUST reject or disadvantage local cameras that do not meaningfully cover the patch target region.
- **FR-008**: The system MUST allow neighbouring/support cameras to be selected when they add meaningful patch-body or boundary coverage.
- **FR-009**: The system MUST NOT reward cameras for seeing halo or spillover content outside the patch target region.
- **FR-010**: The system MUST disadvantage cameras where the patch target occupies only a very small share of the image, while still allowing them when they add otherwise missing target coverage.
- **FR-011**: The system MUST reduce the risk that dense textured regions dominate selection only because they contain many matched points.
- **FR-012**: The system MUST preserve broad local acquisition coverage across the patch body when sparse matched points are weak or unevenly distributed.
- **FR-013**: The system MUST preserve useful boundary support for clean seams and oblique views.
- **FR-014**: The system MUST promote diverse viewing directions when multiple candidates provide otherwise similar target coverage.
- **FR-015**: The system MUST select no more than the configured maximum number of cameras for each patch.
- **FR-016**: The system MUST record, for each patch, selected camera count, local camera count, nonlocal/support camera count, target coverage summary, boundary coverage summary, spillover or target-share warning indicators, and any severe selection warnings.
- **FR-017**: The system MUST produce patch diagnostics that visually distinguish selected local, rejected local, selected support/nonlocal, and unused support/nonlocal cameras.
- **FR-018**: The system MUST include enough diagnostic evidence for a researcher to identify hollow patch interiors, weak boundary coverage, excessive support-camera use, and likely spillover-heavy selections.
- **FR-019**: The system MUST write poor-selector-coverage patches as valid patch outputs by default, keep them trainable by default, and attach clear warnings rather than blocking training automatically.
- **FR-020**: The system MUST treat invalid camera selection inputs, such as missing source sparse outputs or malformed patch metadata, as blocking errors before training begins.
- **FR-021**: The system MUST allow non-critical diagnostic export failures to be logged as warnings when the selected patch dataset itself remains valid.
- **FR-022**: The system MUST keep the existing up-front resume, overwrite, and config-difference behaviour for regenerated patch outputs.
- **FR-023**: The system MUST mark existing patch outputs generated by incompatible selector-affecting settings as requiring an up-front reuse or overwrite decision before any patching work begins.
- **FR-024**: The system MUST keep splat training, cleanup, merging, SOG compression, COLMAP reconstruction, and patch-bound generation outside this feature except where they consume or display selected camera outputs.

### Key Entities *(include if feature involves data)*

- **Patch Target Region**: The stored patch bounds used for selecting images for a trainable patch; includes the existing boundary band but is not expanded again by this feature.
- **Patch Body Coverage**: Evidence that selected cameras cover the interior/body of the patch target region.
- **Patch Boundary Coverage**: Evidence that selected cameras cover the boundary band used to support seam cleanup.
- **Candidate Camera**: Any camera considered for a patch because it is local, neighbouring, observes target-region scene evidence, or geometrically covers the patch target.
- **Selected Camera Set**: The final camera/image set assigned to a patch, constrained by the configured camera limit.
- **Support Or Nonlocal Camera**: A selected or candidate camera whose centre is outside the patch target but may still provide useful target coverage.
- **Spillover Indicator**: A diagnostic signal that a camera likely contains a large amount of content outside the patch target relative to useful target content.
- **Selection Diagnostic**: Human-readable and visual evidence explaining the selected camera set and relevant warnings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the existing Dataset 1 and Dataset 2 patch diagnostics, the Target-Aware Spatial Greedy selector preserves at least 95 percent of local camera-position coverage on average at the project’s normal camera cap while keeping patch-body and boundary coverage at least as high as the current selector baseline.
- **SC-002**: On known problematic reef patches, including Dataset 1 patch `p000`, Dataset 1 patch `p006`, and Dataset 2 patch `p002`, diagnostics show no large unrepresented local acquisition strip after camera selection.
- **SC-003**: On a Polish-town style oblique patch check, the Target-Aware Spatial Greedy selector keeps full patch-body coverage and full boundary coverage while still selecting useful nonlocal/support views.
- **SC-004**: For every generated patch in the validation datasets, the selected camera count is less than or equal to the configured maximum camera count.
- **SC-005**: For every generated patch in the validation datasets, the researcher can inspect local/nonlocal counts, target coverage, boundary coverage, spillover indicators, and selected/rejected camera plots without reading terminal output.
- **SC-006**: Existing patch-output reuse or overwrite decisions are resolved before patch generation starts in 100 percent of tested regeneration scenarios.
- **SC-007**: The Target-Aware Spatial Greedy selector can be run on the small test dataset and at least two large reef dataset patches without launching splat training and without modifying source SfM outputs.

## Assumptions

- Feature 3 already provides patch generation, patch metadata, selected-image export, patch diagnostics, and resume/overwrite handling.
- The stored patch bounds produced by the current patching workflow already include the configured patch buffer; this feature does not create a second buffer.
- The current maximum-cameras-per-patch setting remains the user-facing cap for camera selection.
- The first production implementation should be validated with diagnostics before retraining large patch splats.
- Scratch experiment results are evidence for selecting the new behaviour, but detailed scoring and data-structure choices belong in the implementation plan rather than this specification.
