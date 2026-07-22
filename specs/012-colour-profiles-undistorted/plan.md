# Implementation Plan: Dataset-Specific Undistorted Colour Profiles

**Branch**: `012-colour-profiles-undistorted` | **Date**: 2026-07-22 | **Spec**: [spec.md](spec.md)

## Summary

Reuse the existing colour parameters, GUI keyframes, ordering, interpolation, image writer, SfM workspace and splat source validation. Add a small profile model, exact staging manifest, atomic undistorted-workspace application, explicit profile mode, and optional Nebius profile download.

## Technical Context

**Language/Version**: Python >=3.12 and Bash
**Primary Dependencies**: Existing Pydantic, Click, Pillow, NumPy, PySide6 and PyYAML
**Storage**: Versioned JSON profiles/manifests and run-local image trees
**Testing**: pytest unit/integration tests plus shell syntax checks
**Target Platform**: Ubuntu workstation and headless Nebius workers
**Project Type**: Python CLI/desktop pipeline with shell launchers
**Performance Goals**: Bounded existing image-write concurrency; correct only consumed workspaces
**Constraints**: No new dependency; never mutate raw/SfM inputs; off mode unchanged; atomic publication
**Scale/Scope**: Multi-camera datasets from hundreds to tens of thousands of images and 1024/2048/full workspaces

## Constitution Check

- Reproducibility: PASS; profile hash, mapping, source and application manifest are recorded.
- Observability: PASS; correction progress and completion/failure are recorded.
- Resume/overwrite: PASS; reuse is validated and incompatible replacement remains explicit.
- Modularity/testing: PASS; logic stays in importable colour/SfM/splat modules with focused tests.
- External tools: PASS; external tool behaviour is unchanged.
- Data safety: PASS; raw and SfM inputs remain read-only.

## Project Structure

```text
src/reefs/colour/       profile and workspace application
src/reefs/sfm/          staging mapping production
src/reefs/splat/        corrected workspace selection
src/reefs/experiments/  reusable-source provenance
scripts/nebius/         optional profile transfer
tests/                  focused unit and integration checks
```

**Structure Decision**: Extend existing modules and add only one profile module; avoid a parallel image pipeline.

## Complexity Tracking

No constitution violations.
