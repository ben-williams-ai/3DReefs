# Data Model: Undistorted Colour Profiles

## ColourProfile

- `schema_version`: currently 1.
- `dataset_fingerprint`: hash of ordered original relative paths and stable image attributes.
- `ordered_images`: relative path, camera group, dimensions and content digest for every source image.
- `mode`: `global` or `per_camera`.
- `ordering_method`: recorded ordering contract.
- `keyframes`: edited relative identities, positions and complete colour parameters.
- `created_at`: UTC creation time.

Profiles contain no absolute paths or run state. At least one edited keyframe is required.

## ImageMapping

- Original dataset fingerprint.
- Ordered entries containing original and COLMAP staged relative paths.
- Exact one-to-one membership; duplicate source or destination paths are invalid.

## CorrectedWorkspaceManifest

- Profile mode/hash or gray-world identity.
- Source images/sparse paths and source inventory hash.
- Output path, image count, dimensions/name validation and completion status.
- Corrected workspaces transition from absent to temporary/applying to complete or failed; only complete is reusable.
