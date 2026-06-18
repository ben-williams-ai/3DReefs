# Research: Camera Selection V2

## Decision: Use Scene-Scaled Footprint Targets

The selector will represent each patch by target cells allocated from the full
scene registered-image count and the patch's relative area.

Rationale: This makes target density scale with the dataset rather than using a
fixed square grid that under-samples large or elongated patches.

Alternatives considered:

- Fixed grid per patch: rejected because it was too coarse for known reef
  failures and does not scale with patch size.
- Sparse points only: rejected because low-texture reef areas can have weak
  sparse evidence despite real image coverage.
- Mesh or alpha-shape target: deferred because it adds parameters and still
  cannot recover scene parts absent from the sparse model.

## Decision: Use Aspect-Aware Footprint Cells

Each patch target representation will follow the patch width/height ratio.

Rationale: Long or thin patches need coverage cells distributed across their
actual footprint, not squeezed into a square target pattern.

Alternatives considered:

- Square grid: rejected because it can hide gaps along long patch dimensions.
- Camera-count-only cells: rejected because patch area and aspect both matter.

## Decision: Use Adaptive Per-Cell Heights

Cells with reliable local sparse points use representative local heights. Cells
with too little evidence look at neighbouring cells, then robust patch-level
height. Flat areas use fewer heights; vertically varied areas can use more.

Rationale: Reef patches are often flat enough for simple height samples, while
Polish-town style patches may need multiple heights to represent useful vertical
structure.

Alternatives considered:

- One patch-wide height: rejected because it misses tall structures.
- Hard-coded low/mid/high heights everywhere: rejected because it is wasteful
  and arbitrary for flat reef scenes.

## Decision: Use Either Track Or Geometric Visibility Evidence

A camera can be useful when either matched scene evidence or geometric footprint
visibility supports it. Target image share then helps rank candidates and reject
tiny sliver views.

Rationale: Matched tracks are reliable where present, but low-texture reef areas
need geometric footprint visibility to avoid being ignored.

Alternatives considered:

- Require both tracks and geometry: rejected because it fails low-texture reef
  cases.
- Use geometry only: rejected because track evidence is valuable for real
  observed structure and Polish-town façades.

## Decision: Candidate External Cameras

External candidates come from one-ring neighbouring patch cameras plus any
camera with direct matched-track or geometric footprint evidence for the patch.

Rationale: One-ring neighbours keep the candidate set small and relevant, while
direct target evidence prevents missing useful non-neighbour cameras.

Alternatives considered:

- Whole-scene geometric candidates only: rejected as slower and noisier.
- One-ring neighbours only: rejected because direct target evidence can reveal
  useful cameras outside the immediate neighbour set.

## Decision: Marginal Selection Until Cap Or No Useful Candidates

Cameras are selected by additional useful footprint coverage, track evidence,
target image share, and small diversity/tie-break signals. Selection continues
until the configured cap is reached or no useful candidates remain.

Rationale: A static global ranking can over-select redundant cameras. Marginal
selection better preserves coverage diversity while respecting the cap.

Alternatives considered:

- Stop when marginal gain becomes non-positive: rejected because it previously
  left useful capacity unused.
- Fixed external quota: rejected because the spec requires usefulness-based
  internal/external competition, not a quota.

## Decision: Diagnostics-Only Acceptance

Feature 006 is accepted using patch-selection diagnostics. Splat training,
merge, and visual splat inspection are not required for this feature.

Rationale: This feature changes patch camera selection. Expensive training
belongs to later validation once diagnostics show the selector is sane.

Alternatives considered:

- Full training gate: rejected as too expensive and outside feature scope.
- No real patch diagnostics: rejected because synthetic tests alone cannot catch
  the observed camera-selection failures.
