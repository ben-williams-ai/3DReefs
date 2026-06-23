# COLMAP SfM Requirements Checklist

**Purpose**: Validate that the Feature 2 requirements and plan are complete enough for implementation.  
**Created**: 2026-06-10  
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [x] CHK001 Are the raw-image SfM/COLMAP undistortion requirements distinct from recoloured-image splatting input requirements? [Completeness, Spec FR-002, FR-012, FR-013]
- [x] CHK002 Are single-camera and multi-camera layouts both described with clear behaviour for direct images and camera subfolders? [Completeness, Spec US2, FR-003]
- [x] CHK003 Are invalid image-layout and per-camera dimension cases required to fail before heavy SfM work? [Completeness, Spec US2, SC-002]
- [x] CHK004 Are mixed camera-source metadata warnings specified for interactive and non-interactive runs? [Completeness, Spec FR-006, FR-008]
- [x] CHK005 Are user-supplied intrinsics, default intrinsics pre-calculation, and insufficient calibration-image cases all covered? [Completeness, Spec FR-016, FR-017, FR-018, FR-019]
- [x] CHK006 Are all user-visible matching choices and their required supporting resources specified? [Completeness, Spec FR-025, FR-026, FR-027, FR-028]
- [x] CHK007 Are global and incremental reconstruction behaviours defined without legacy standalone GLOMAP or silent fallback? [Completeness, Spec FR-029, FR-030, FR-031, FR-032]
- [x] CHK008 Are multiple sparse-model selection and reporting requirements measurable? [Completeness, Spec FR-035]
- [x] CHK009 Are dense and mesh outputs clearly optional, disabled by default, and bounded to this feature's scope? [Completeness, Spec US5, FR-038, FR-039, FR-040, FR-041]
- [x] CHK010 Are SfM resume, reuse, rerun, and overwrite decisions required before any requested stage starts? [Completeness, Spec US6, FR-044, FR-045, FR-046]

## Requirement Clarity

- [x] CHK011 Is "before heavy SfM work" tied to concrete preflight outcomes such as failing before feature extraction or matching? [Clarity, Spec SC-002, FR-027, FR-028]
- [x] CHK012 Is the default vocabulary-tree requirement explicit enough for a user to know they must configure the resource? [Clarity, Spec FR-028, Plan config contract]
- [x] CHK013 Is the selected splatting image source unambiguous when recoloured images are enabled, while COLMAP undistortion remains raw-only? [Clarity, Spec US4, FR-013]
- [x] CHK014 Are "supported backend" and "no silent fallback" reflected in both user-visible requirements and implementation planning? [Consistency, Spec FR-032, FR-033, Plan]
- [x] CHK015 Are public-path safety requirements present without embedding private local paths in public docs? [Consistency, Spec FR-047]

## Acceptance Criteria Quality

- [x] CHK016 Can success be measured by inspecting sparse output, undistorted output, timings, command logs, and run status? [Measurability, Spec SC-001, SC-004]
- [x] CHK017 Are failure criteria measurable for invalid layouts, invalid camera files, missing vocab tree, unsupported backends, and recoloured mismatches? [Measurability, Spec SC-002]
- [x] CHK018 Are stage-timing requirements specific enough to drive implementation and tests? [Measurability, Spec FR-043]

## Scenario And Edge Case Coverage

- [x] CHK019 Are recovery flows covered when prior outputs or partial SfM runs already exist? [Coverage, Spec US6]
- [x] CHK020 Are unsupported or missing external COLMAP capabilities covered before expensive work starts? [Coverage, Spec FR-033]
- [x] CHK021 Are spatial matching and optional pose-prior requirements bounded so underwater defaults do not depend on GPS/EXIF? [Coverage, Spec FR-009, FR-010, FR-027]
- [x] CHK022 Is the exclusion boundary for splatting, NanoGS, LOD, PlayCanvas packaging, and mega-patching explicit? [Coverage, Spec FR-048]

## Technical Placement

- [x] CHK023 Are command mappings, module layout, and subprocess implementation details kept in plan/contracts rather than spec? [Placement, Plan, Contracts]
- [x] CHK024 Are the required config settings and defaults captured in the config contract rather than only in prose? [Placement, Plan config contract]
- [x] CHK025 Are test expectations for mocked automated tests and local smoke runs represented in plan/quickstart rather than the user-facing spec? [Placement, Plan, Quickstart]
