# Research: Hybrid Camera Selection

## Decision: Use One Target-Aware Spatial Greedy Selector

The production selector will be the Target-Aware Spatial Greedy selector. It
combines track visibility, geometric target visibility, spillover avoidance, view
diversity, and a small spatial acquisition-coverage term. It replaces the
existing old boundary-first balanced selector as the single supported approach.

Rationale: Scratch experiments showed this policy gave the best balance across
reef and Polish-town style data. At the normal reef cap it preserved almost all
local camera-position coverage while keeping core and boundary target coverage at
least as high as the current selector.

Alternatives considered:
- Current boundary-first balanced selector: strong for edges, but can hollow out
  low-texture reef patch bodies.
- Tracks-only greedy: better than current on reefs, but still weak where sparse
  tracks are uneven.
- Projection-only greedy: rejects cameras that point away, but over-trusts the
  geometric proxy and can over-select nonlocal support cameras.
- Fixed support quota: simple, but cannot adapt across reef transects and
  oblique urban/drone patches.

## Decision: Treat Stored Patch Bounds As The Target Region

Camera selection will use the stored patch bounds as the target/training region.
It will not expand those bounds a second time.

Rationale: Feature 3 patch bounds already include the configured scene-relative
buffer used by cleanup. Expanding again would reward halo content and change
what cleanup expects to trim.

Alternatives considered:
- Expand bounds during selection: rejected because it repeats a historical source
  of confusing patch borders.
- Require separate core and buffered bounds now: deferred until there is evidence
  it improves selection enough to justify a metadata change.

## Decision: Use A Bounded Patch Target Proxy

The first production target proxy will use bounded samples inside the patch
bounds, with a robust local Z value derived from sparse points in and near the
patch. Samples are labelled body-like or boundary-like using the existing
boundary band.

Rationale: This is fast, deterministic, enough for low-texture reef protection,
and avoids adding heavy meshing or alpha-shape dependencies.

Alternatives considered:
- Alpha shapes or voxel occupancy: potentially more geometric, but too much
  complexity before seeing evidence that it changes decisions.
- Sparse points only: misses low-texture regions where the camera survey still
  covered the patch.

## Decision: Combine Track Evidence And Projection Evidence With Either-Signal Fusion

Each candidate camera gets target evidence from COLMAP tracks and from geometric
projection of target samples. The two signals are fused so either strong signal
can make a camera useful, while both weak means the camera is poor.

Rationale: Tracks are real matched visibility where they exist; projection
protects low-texture areas and catches cameras that look into a patch even when
few points were reconstructed there.

Alternatives considered:
- Simple average: can dilute one strong, trustworthy signal.
- Tracks only: fails low-texture and sparse-hole cases.
- Projection only: ignores real matched visibility and occlusion evidence.

## Decision: Density-Weight Sparse Tracks

Sparse points inside dense cells will contribute less than isolated points, using
a simple grid-density weight in the first implementation.

Rationale: Dense coral, building detail, or other textured clusters can dominate
raw point-count ranking even when other patch areas need coverage more.

Alternatives considered:
- Raw point counts: too biased toward textured clusters.
- k-nearest-neighbour density: useful later, but grid weighting is simpler and
  adequate for the first production version.

## Decision: Use Greedy Marginal Selection

The selector will pick cameras one at a time by the marginal target coverage and
diversity they add to the current selected set. The marginal score includes body
coverage, boundary coverage, local camera-position cell protection,
view-direction diversity, target-image-share penalty, soft nonlocal penalty, and
redundancy penalty.

Rationale: A global ranking can repeatedly select cameras that see the same
feature-rich area. Marginal selection is a better fit for patch coverage.

Alternatives considered:
- Sort once by boundary-first score: preserves edges but can replace important
  body cameras.
- Optimisation/ILP: unnecessary for this stage and harder to maintain.

## Decision: Keep Nonlocal Status As A Soft Prior

Local and support cameras compete on target usefulness. Nonlocal/support status
is recorded and can be softly penalised as nonlocal share rises, but it is not a
hard quota or hard block.

Rationale: Polish-town style oblique scenes need strong nonlocal support. Reef
patches need protection from support cameras replacing too much body coverage.

Alternatives considered:
- Always keep locals first: fails when local cameras point away.
- Fixed support percentage: not robust across survey styles.

## Decision: Poor Selector Coverage Warns But Does Not Block Training

When inputs are valid but coverage is weak, the patch remains trainable by
default and receives explicit warnings in metadata, diagnostics, and run records.

Rationale: Researchers may still want to inspect or train the patch; blocking
should be reserved for invalid inputs or invalid patch artefacts.

Alternatives considered:
- Block poor-coverage patches: too aggressive for exploratory datasets.
- Silently continue: repeats past observability problems.

## Decision: No Public Selector Mode

This feature will not add a config switch between old and new selectors. The
Target-Aware Spatial Greedy selector becomes the only supported behaviour.

Rationale: Multiple modes increase maintenance load and make experiment outputs
harder to compare. Historical selectors remain evidence in scratch reports, not
runtime choices.

Alternatives considered:
- Keep a legacy selector flag: rejected to keep the pipeline simpler.
