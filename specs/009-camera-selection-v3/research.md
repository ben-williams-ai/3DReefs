# Research: Camera Selection V3

## Decision: Replace the old selector, do not add modes

**Rationale**: The implementation plan calls for one production selector. Keeping old and V3 modes would add patch-affecting state and make reuse decisions harder without preserving a desired production path.

**Alternatives considered**: A config-driven selector mode was rejected because V2 and the old selector are superseded for this feature.

## Decision: Generate patch bounds with the internal camera target

**Rationale**: `wildflow.splat.patches` currently receives `max_cameras`. V3 reserves part of the final cap for external support, so wildflow should receive `max_cameras - floor(max_cameras * external_support_fraction)`. This preserves the invariant that useful internal cameras fit within the final cap.

**Alternatives considered**: Using the final cap for wildflow was rejected because it repeats the external-support crowding failure.

## Decision: Use exactly three usefulness signals

**Rationale**: V3 needs simple evidence that maps to the known failure: a camera is useful when enough of the target appears in the image and it has either COLMAP track evidence or full patch/frustum footprint overlap.

**Alternatives considered**: Boundary/edge/buffer scoring and sparse-density area scoring were rejected because the V3 source of truth explicitly removes them.

## Decision: Use rectangle/frustum geometry, not sparse-point geometry

**Rationale**: The patch footprint is the raw rectangle from wildflow bounds. For each candidate camera, V3 projects the image-corner frustum to the scene XY plane, intersects that frustum footprint with the patch rectangle, and projects the intersection polygon back into the image for target-image-share scoring. Sparse points remain useful, but only for the separate track-count signal.

**Alternatives considered**: Convex hulls or bounding boxes of observed sparse points were rejected because they measure sparse reconstruction density, not the full patch target requested by V3.

## Decision: Treat full nested bounds as the patch footprint

**Rationale**: Existing patch metadata already stores canonical nested bounds and post-processing depends on that shape. V3 uses the whole rectangle, including buffer, for footprint overlap and internal-camera classification.

**Alternatives considered**: Target grids, height models, sparse-point-derived footprints, and body/buffer roles were rejected as extra machinery not needed for the current failure.

## Decision: Restrict external candidates to one-ring neighbours

**Rationale**: Existing code already discovers one-ring neighbours, and the spec requires no global external search. This keeps selection bounded and explainable.

**Alternatives considered**: Searching all cameras was rejected because it can add unrelated views and undermine internal-first selection.

## Decision: Rank external support with evidence plus azimuth spread

**Rationale**: External support should add useful oblique context without letting weak diverse views win. The planned 0.75 evidence / 0.25 azimuth score is fixed for the first validation.

**Alternatives considered**: Pure evidence ranking was rejected because it can over-select one direction; sector quota balancing was rejected because V3 only needs greedy support diversity, not old selector behaviour.

## Decision: Preserve diagnostic filenames, change contents

**Rationale**: Users already inspect `camera_coverage.csv`, `plot.png`, `plot.html`, `histogram.png`, and `generation.log`. Keeping names avoids changing review habits while allowing V3-specific columns and categories.

**Alternatives considered**: New V3 filenames were rejected as needless churn.

## Decision: Validate diagnostics before LFS

**Rationale**: Splat training is expensive. The first pass should generate PNG sweeps, summaries, and known-bad comparisons, then wait for visual approval.

**Alternatives considered**: Running LFS immediately was rejected because bad selection is cheaper to catch in diagnostic plots.
