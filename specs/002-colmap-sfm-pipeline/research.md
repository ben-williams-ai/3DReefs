# Research: COLMAP SfM Pipeline

## Decision: Extend Feature 1 Run Records For SfM

**Decision**: Store SfM outputs under the active run directory:
`<project.dir>/runs/<run_id>/sfm/`, with `logs/colmap.log` and diagnostics
alongside the existing manifest/status/timings records.

**Rationale**: Feature 1 already gives reproducible run IDs, effective configs,
CLI override records, resume decisions, and timings. Keeping SfM outputs inside
the same run preserves provenance and makes later splatting stages point at one
completed run rather than mixing project-global artefacts.

**Alternatives considered**:
- Project-global `colmap/` output directory: rejected because repeated
  experiments would overwrite or cross-contaminate outputs.
- Old repo's separate `paths.output` style: useful evidence, but less aligned
  with Feature 1's run-record model.

## Decision: Vocabulary Tree Is Required When Selected Matching Uses It

**Decision**: Add a mandatory configured vocabulary-tree path for any selected
matching mode that includes vocabulary-tree retrieval, including the default
`sequential_vocab_tree` mode.

**Rationale**: The default matching strategy needs local sequential matching plus
vocabulary-tree recovery/loop matching. Continuing without the vocabulary tree
would silently weaken the selected matching strategy and make experiments
harder to compare.

**Alternatives considered**:
- Warn and continue sequential-only: rejected as a silent behavioural downgrade.
- Auto-switch to exhaustive matching: rejected because it changes runtime and
  matching semantics.
- Disable vocabulary-tree matching by default: rejected because the guide makes
  sequential plus vocabulary-tree the desired reef default.

## Decision: Explicit COLMAP Command Builders With Help Validation

**Decision**: Implement command builders for feature extraction, matchers,
global/incremental reconstruction, undistortion, dense stereo, fusion, and mesh.
Validate selected commands/options against the active COLMAP `4.0.4` help output
where feasible before running heavy work.

**Rationale**: The old repo's flag-audit approach caught backend drift, and the
guide warns that old flags may not match current tool versions. Explicit command
builders keep tests focused and avoid fragile shell string assembly.

**Alternatives considered**:
- Hand-write shell command strings in the orchestration layer: rejected as hard
  to test and easy to mistype.
- Copy old command builder code directly: rejected because the old repo contains
  legacy standalone GLOMAP and older architecture decisions.

## Decision: Raw Images For SfM, Recoloured Images Only For Undistortion

**Decision**: Feature extraction, matching, and sparse reconstruction always use
raw images. If `project.recolour_images` is true, the undistortion image source
is the validated recoloured mirror with matching relative names and dimensions.

**Rationale**: Raw images are expected to be more reliable for SfM. Recoloured
images are appearance-oriented and useful for later splatting. COLMAP
undistortion can use a different image root if relative names and dimensions
match the sparse model; this must be covered by integration tests with mocked or
tiny fixtures before relying on it in large runs.

**Alternatives considered**:
- Use recoloured images for SfM too: rejected by the guide.
- Delay recoloured validation until undistortion: rejected because failures
  should be detected before heavy work wherever possible.

## Decision: Intrinsics Pre-Calculation Uses Sequence Index Defaults

**Decision**: Default intrinsics pre-calculation uses per-camera sequence windows:
images 50-149 when at least 150 images exist; the best available 100 after
skipping early frames where possible when fewer than 150 exist; all suitable
available images with a warning when fewer than 100 exist.

**Rationale**: The guide explicitly replaces old translation/GPS-heavy subset
selection for underwater data, where GPS is unavailable. The default still
avoids the earliest unstable frames where possible.

**Alternatives considered**:
- Old GPS/translation-heavy selector: retained only as future/terrestrial
  inspiration, not default reef behaviour.
- Fail on short sequences: rejected because small test datasets and short reef
  segments should still be usable.

## Decision: Multiple Sparse Models Are Resolved By Registered Image Count

**Decision**: When reconstruction produces multiple sparse models, select the
model with the most registered images for undistortion/downstream stages. Record
registered image count and 3D point count for every produced model and warn.

**Rationale**: Registered image count is the clearest measure of dataset coverage
for reef splatting handoff. Recording all model counts preserves evidence when a
secondary model may represent a disconnected survey segment.

**Alternatives considered**:
- Fail by default: safer but would interrupt runs the user explicitly wants to
  automate.
- Select by 3D point count: rejected because a dense small component may have
  more points but poorer image coverage.
- Carry all models forward: deferred; later patching/splatting expects one
  selected SfM handoff.

## Decision: Mixed Camera Metadata Requires Up-Front User Intent

**Decision**: If metadata suggests mixed camera sources within a camera group,
interactive runs prompt before SfM starts. Non-interactive runs fail unless an
explicit proceed setting is pre-supplied.

**Rationale**: Mixed sources in one camera group can invalidate per-camera
intrinsics, but metadata can be imperfect. A beginner-friendly prompt makes the
risk visible without blocking valid data unnecessarily. Non-interactive runs
must not surprise the user mid-run.

**Alternatives considered**:
- Always fail: too strict when metadata is misleading.
- Warn and continue: too risky for intrinsics.
- Ignore metadata consistency: rejected because it hides a common data-prep
  problem.

## Decision: Dense And Mesh Are Optional Comparison Outputs

**Decision**: Dense point cloud and mesh stages are disabled by default and run
only when explicitly enabled. Mesh requires dense prerequisites.

**Rationale**: The main pipeline target is splatting. Dense/mesh can be expensive
but useful for small comparison experiments, so they should be opt-in and timed.

**Alternatives considered**:
- Run dense by default: rejected due to runtime and storage cost.
- Exclude dense/mesh entirely: rejected because the spec asks for optional
  comparison outputs.
