# Research: Undistorted Colour Profiles

## Decision: Correct appearance after undistortion

Correction changes colour only and must preserve the exact pixels-to-camera relationship. Therefore corrected copies come from each consumed undistorted image tree and reuse that workspace's sparse model.

## Decision: Dataset-specific versioned profiles

The current GUI edits evenly selected original-image keyframes and linearly interpolates parameters. A profile records those relative identities and rejects other datasets; normalised cross-dataset transfer is intentionally excluded.

## Decision: Persist staging identity

COLMAP-safe names are deterministic but currently lose original identity. SfM will persist the exact mapping; strict deterministic reconstruction is retained only for legacy sources.

## Decision: Explicit profile mode

`profile` is separate from `manual`, so headless behaviour is visible and `off` can remain an auditable no-op. Gray-world reuses the same undistorted application path.

## Decision: Atomic run-local outputs

Write to a sibling temporary directory, validate names/dimensions/RGB and manifest, then rename. SfM workspaces and project-level legacy outputs remain untouched.
