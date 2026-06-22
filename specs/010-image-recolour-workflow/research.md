# Research: Optional Image Recolour Workflow

## Decision: Use A Dedicated `reefs.colour` Package

**Rationale**: Colour restoration has independent ordering, state, interpolation, filtering, GUI, and standalone CLI concerns. A dedicated package keeps pipeline orchestration thin and satisfies the constitution's modularity requirement.

**Alternatives considered**:
- Put all logic in `reefs.cli`: rejected because it would make state, GUI, and filter behaviour hard to test.
- Fold colour logic into `reefs.sfm`: rejected because colour restoration can run standalone and is not part of SfM geometry estimation.

## Decision: Keep Existing Config Shape And Add `project.start_sfm_immediately`

**Rationale**: The repository already uses `project.recolour_images`, `advanced.paths.recoloured_images_dir`, and `advanced.sfm.undistortion.image_source`. The plan extends this shape by adding `project.start_sfm_immediately: true` and documenting `project.recolour_images: false` in examples, avoiding a breaking top-level config move.

**Alternatives considered**:
- Add root-level `recolour_images`: rejected because current typed config already places project-level switches under `project`, and moving it would break existing tests/configs.
- Put all colour options under `advanced`: rejected because enabling/disabling the workflow is a primary project-level behaviour.

## Decision: Shared Ordering Helper With Metadata-First, Natural-Path Fallback

**Rationale**: Existing image layout detection uses sorted filenames, which is insufficient for names such as `img1`, `img2`, `img10`. A shared ordering helper should try reliable capture metadata first, then natural-sort relative paths with stable tie-breaking. It will be reused by image layout, intrinsics subset selection, patch ordering where order matters, and colour keyframe/interpolation logic.

**Alternatives considered**:
- Lexicographic sorting: rejected because it is explicitly called out as wrong for numbered sequences.
- Require timestamps: rejected because many datasets may have missing or inconsistent metadata.
- Per-call sorting rules: rejected because it would make ordering drift likely.

## Decision: JSON State File In Run Colour Directory

**Rationale**: JSON is already used for run manifests/status and is easy to validate against a schema. Store colour state under `<run_dir>/colour_restoration/state.json` so it is tied to a run and can be resumed, documented, and inspected.

**Alternatives considered**:
- YAML state: rejected because JSON schema validation is simpler for tests and contracts.
- Store state next to `recoloured_images`: rejected because run-specific session status and handoff paths belong with run artefacts.

## Decision: One Canonical Corrected Image Set Per Run

**Rationale**: The clarification decision states that reapplying colour restoration replaces the existing corrected image set only after an explicit overwrite warning. This keeps downstream handoff logic simple while protecting the user from accidental replacement.

**Alternatives considered**:
- Version every corrected set: rejected because downstream selection becomes more complex and storage grows quickly.
- Keep automatic previous backup: rejected for v1 because it adds storage and cleanup policy that the spec does not require.

## Decision: PySide6 Desktop GUI With Testable Non-GUI Core

**Rationale**: The original prompt requires PySide6 and a local desktop GUI, not a web app. The implementation should isolate GUI widgets from state, ordering, interpolation, and filter logic so most behaviour is testable without a display server.

**Alternatives considered**:
- Web UI: rejected by explicit prompt.
- CLI-only tuning: rejected because the feature requires image previews and interactive controls.

## Decision: Port The Provided Wildflow-Style Filter Stack Into A Local Module

**Rationale**: The prompt makes the script the source of truth for operation order, defaults, device selection, and valid ranges. A local `filters.py` can preserve that behaviour, expose testable functions, and avoid depending on a gist or undocumented external API.

**Alternatives considered**:
- Call a remote or copied standalone script: rejected because it would be harder to test and integrate with batching/progress/state.
- Use generic image adjustment libraries only: rejected because operation order and parameter semantics must match the provided script.

## Decision: Full-Resolution Batch Processing, Downscaled Previews Only In GUI

**Rationale**: The spec requires final outputs to preserve dimensions and not accidentally save previews. GUI preview generation can use downscaled images for responsiveness, but batch apply must reload source images at full resolution.

**Alternatives considered**:
- Reuse preview arrays for output: rejected because it risks resizing/cropping final images.
- Process only one image at a time: rejected because batch processing and progress are required for large datasets.

## Decision: Splat Wait Gate Reads Colour State

**Rationale**: Splatting must never start while colour restoration is incomplete, active, or applying. The splat preflight/validation path is the natural gate because it already validates the standard `sfm/undistorted` handoff before downstream training.

**Alternatives considered**:
- Let LFS fail on missing images: rejected because it wastes long-running jobs and violates the spec.
- Add special LFS input handling: rejected because downstream stages must consume the standard handoff.

## Decision: Standalone Colour Command Shares The Same State And Apply Logic

**Rationale**: Users need to run colour restoration independently of SfM/splatting and reopen a run after reviewing outputs. A command such as `uv run main.py colour --config ... --run-id ...` or equivalent Click subcommand should call the same state/GUI/apply services used by the pipeline path.

**Alternatives considered**:
- Separate script outside the package: rejected because it would bypass config, run records, and tests.
- Full pipeline invocation with special `--steps`: possible, but less discoverable than a documented colour command; implementation may still support a `colour` step alias if it fits existing CLI patterns.

## Decision: Documentation In README Plus Focused Quickstart

**Rationale**: README is the user-facing place for pipeline commands. The feature also needs a quickstart in the Spec Kit artefacts to drive implementation and acceptance.

**Alternatives considered**:
- Only generated Spec Kit docs: rejected because normal users may not read specs.
- Only code comments: rejected because workflows and commands must be discoverable.
