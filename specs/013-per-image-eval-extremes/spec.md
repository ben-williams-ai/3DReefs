# Feature Specification: Per-Image Evaluation Extremes

**Feature Branch**: `feature/per-image-eval-extremes`
**Created**: 2026-07-24
**Status**: Complete
**Input**: Produce a complete, provenance-backed per-image evaluation dataset and deterministic LPIPS extremes for the accepted Dataset 1–6 Stage 2 patches, primarily from authoritative saved render pairs.

## User Scenarios & Testing

### User Story 1 - Recover authoritative per-image metrics (Priority: P1)

As a researcher, I can recover LPIPS, PSNR and SSIM for every accepted final-step image without retraining or substituting aggregate metrics.

**Why this priority**: Complete per-image evidence is the scientific basis for every later ranking and export.

**Independent Test**: Inventory and score one accepted patch, then prove its image count, identities, checksums and aggregate means against authoritative metadata.

**Acceptance Scenarios**:

1. **Given** an accepted patch with complete final comparison images and mapping metadata, **When** it is processed, **Then** one provenance-complete row is produced for every final comparison image.
2. **Given** missing, duplicate, malformed, mismatched or non-finite input, **When** validation runs, **Then** processing fails explicitly without silently emitting accepted scores.
3. **Given** future normal evaluation, **When** Python-owned metrics are written, **Then** canonical per-image metrics are retained while existing aggregate `metrics.csv` semantics remain unchanged.

---

### User Story 2 - Export deterministic visual extremes (Priority: P2)

As a researcher, I can inspect the three lowest- and three highest-LPIPS images for every accepted patch as separate lossless ground-truth, render and comparison files.

**Why this priority**: Extreme examples make metric behaviour and pipeline defects reviewable.

**Independent Test**: Export one patch twice and confirm identical selections, names, checksums and correctly split image halves.

**Acceptance Scenarios**:

1. **Given** at least six scored images, **When** extremes are exported, **Then** exactly three best and three worst rows are selected by LPIPS with image-name tie-breaking.
2. **Given** fewer than six images, **When** extremes are exported, **Then** all unique images are exported and any overlap is documented rather than duplicated.
3. **Given** an exported selection, **When** it is visually inspected, **Then** GT is left, render is right, the separator is absent and dimensions/orientation match.

---

### User Story 3 - Audit the complete six-dataset result (Priority: P3)

As a researcher, I can verify the accepted attempts, raw downloads, combined scores, metric reproduction and visual inspection from durable manifests.

**Why this priority**: Scientific results must be traceable and resumable.

**Independent Test**: Validate the final report and manifests against all accepted source objects and generated files.

**Acceptance Scenarios**:

1. **Given** the six accepted run families, **When** inventory completes, **Then** exactly ten accepted 2048/200/2M patches per dataset are identified or a source-defined exception is evidenced.
2. **Given** all accepted inputs, **When** processing completes, **Then** the combined CSV contains every accepted final-step image exactly once.
3. **Given** an interrupted transfer or scoring run, **When** it resumes, **Then** verified files are reused and raw inputs are not overwritten.

### Edge Cases

- Accepted-attempt evidence differs between original and retry prefixes.
- Comparison indices are missing, duplicated, non-numeric or have unexpected extras.
- Reordered sparse records and `test_every` do not yield the manifest holdout set.
- A composite has the wrong four-pixel separator geometry, mismatched halves or implausible dimensions.
- PSNR is infinite because GT and render are identical; other non-finite values remain invalid.
- Existing `data/patch-results/` contains partial work and must be checksum-validated before resume or archived safely.
- Historical aggregate values differ from recomputed means beyond rounding tolerance.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST identify the accepted attempt and exactly ten scientifically accepted 2048-resolution, 200-camera, 2,000,000-Gaussian patches for each Dataset 1–6 using terminal evidence.
- **FR-002**: The system MUST prefer authoritative saved final-step comparison images and MUST NOT retrain, rerun SfM or evaluate again unless required accepted evidence is missing or corrupt.
- **FR-003**: The system MUST prove comparison-index-to-original-image-name mapping from reordered eval sparse records and `test_every`; positional inference from a manifest alone is forbidden.
- **FR-004**: The system MUST compute per-image LPIPS with AlexNet and `[-1, 1]` normalisation, plus PSNR and SSIM using the existing Python-owned implementations and parameters.
- **FR-005**: Normal future evaluation MUST write canonical `per_image_metrics.csv` while preserving aggregate `metrics.csv`, return types and public caller behaviour.
- **FR-006**: Historical backfill MUST emit the required per-image CSV fields, POSIX relative image names, source checksums and provenance for every accepted image.
- **FR-007**: The system MUST reject duplicate/missing indices, count mismatches, malformed composites, mismatched dimensions, missing mapping inputs and invalid metric values.
- **FR-008**: Ranking MUST be deterministic: ascending LPIPS for best and descending LPIPS for worst, with original relative image name as tie-breaker.
- **FR-009**: Each patch MUST export lossless separate GT/render images, retain or link the comparison image, and write a checksum-bearing selection CSV.
- **FR-010**: Raw downloads MUST remain unchanged and separate from scores and exports under ignored `data/patch-results/`.
- **FR-011**: Downloads, checksums, scoring and exports MUST be resumable, monitored to verified terminal outcomes and recorded in manifests.
- **FR-012**: The complete output MUST include per-dataset CSVs, one combined CSV, accepted-run/download/checksum inventories, validation report and visual-inspection manifest.
- **FR-013**: Aggregate per-patch metric means MUST reproduce historical accepted metrics within documented rounding tolerance or processing MUST stop for investigation.
- **FR-014**: A fallback MUST be evaluation-only from accepted 2M PLY and existing sources, must use a new retry prefix, and must never invoke training or SfM.
- **FR-015**: No downloaded or generated dataset artefacts, secrets or private infrastructure values may enter Git.

### Key Entities

- **Accepted patch**: Dataset, patch identity, run/attempt, terminal status, iteration, Gaussian count and authoritative object prefix.
- **Comparison mapping**: Comparison index, reordered sparse position, `test_every`, original relative image name and manifest identity.
- **Per-image score**: Required CSV identity, dimensions, metrics, provenance, checksums, status and failure reason.
- **Extreme selection**: Patch, best/worst class, rank, source score row and exported file checksums.
- **Processing manifest**: Input/output inventories, software provenance, completion state and validation evidence.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All six datasets and sixty accepted patches are represented, unless a differing accepted set is proven and documented.
- **SC-002**: The combined CSV row count exactly equals the verified accepted final-comparison inventory (preliminary expectation: 898).
- **SC-003**: Every accepted comparison has exactly one unique patch/index row and one unique patch/image-name row.
- **SC-004**: Every patch with at least six images has exactly three best and three worst selections, reproducible across repeated runs.
- **SC-005**: All source and exported files pass checksum/decode/dimension validation, and raw source checksums remain unchanged after export.
- **SC-006**: Recomputed per-patch aggregate metrics match accepted historical metrics within documented CSV rounding tolerance.
- **SC-007**: Real-image inspection covers best and worst outputs from every dataset and multiple patches per dataset with no unresolved split, colour, crop, orientation or corruption defect.
- **SC-008**: Focused tests, configured static checks and proportionate regression tests pass before code is merged.
- **SC-009**: No unnecessary evaluation rerun occurs and no Nebius VM remains billable.

## Assumptions

- The accepted S3 families and preliminary counts in the task prompt are authoritative starting points but still require terminal verification.
- The four-pixel composite layout and existing Python metric implementations remain the canonical scientific definitions.
- Local GPU capacity is sufficient for sequential LPIPS scoring; batching is optional only if measured and scientifically identical.
- The ignored local data tree is the durable delivery location; Git contains only reusable code, tests and public-safe Spec Kit artefacts.

## Non-Goals

- Retraining splats, rerunning SfM, changing the selected ablation cell or ranking by a metric other than LPIPS.
- Building a second metric framework, adding dependencies or changing existing aggregate CSV meaning.
- Downloading intermediate steps or other Gaussian-budget cells without specific validation evidence.
