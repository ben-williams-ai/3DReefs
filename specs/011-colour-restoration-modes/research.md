# Research: Colour Restoration Modes

## Decision: Use a top-level colour restoration config model

**Decision**: Add a required top-level `colour_restoration` block with `mode`, `overwrite`, and `start_sfm_immediately`, while removing colour workflow settings from `project`.

**Rationale**: The setting no longer describes a project directory property; it describes workflow behaviour. A top-level block keeps related mode, reuse, and manual-SfM controls together and makes legacy `project.recolour_images`/`project.start_sfm_immediately` clearly invalid through existing `extra="forbid"` validation.

**Alternatives considered**:

- Keep `project.colour_restoration`: rejected because reuse and manual-SfM controls would remain scattered under `project`.
- Use `colour_restoration.colour_restoration`: rejected during clarification because the doubled name is hard to read and error-prone.

## Decision: Represent modes with a string enum

**Decision**: Add a `ColourRestorationMode` enum with `off`, `gray_world`, and `manual`, exposed as `colour_restoration.mode`.

**Rationale**: Pydantic enum validation gives clear allowed values, typed downstream checks, and simple CLI override parsing. It also avoids boolean branching that cannot represent all behaviours.

**Alternatives considered**:

- Keep a boolean plus extra switches: rejected because it preserves ambiguity and compatibility traps.
- Free-form strings: rejected because invalid modes should fail clearly at config load.

## Decision: Reuse existing colour pipeline primitives for gray-world

**Decision**: Implement `gray_world` through the existing full-resolution colour apply path using `ColourParameterSet(gray_world=1.0)` for every image.

**Rationale**: The existing image traversal, output validation, worker bounding, RGB conversion, and dimension checks already satisfy most automatic-mode requirements. Reusing them reduces risk and keeps raw images read-only.

**Alternatives considered**:

- Add a separate gray-world writer: rejected because it would duplicate validation and output-tree semantics.
- Invoke the GUI in a scripted mode: rejected because the requirement explicitly skips the GUI.

## Decision: Make overwrite mode-wide for same-run outputs

**Decision**: Apply `colour_restoration.overwrite` to same-run restored outputs in both `gray_world` and `manual` modes.

**Rationale**: Users get one predictable switch for reuse versus regeneration. It aligns with the constitution requirement that overwrite intent is explicit before expensive/destructive output replacement.

**Alternatives considered**:

- Limit overwrite to gray-world: rejected because manual output regeneration also needs explicit config-driven behaviour.
- Always prompt: rejected for unattended pipeline runs and because preflight should collect decisions up front where possible.

## Decision: Keep SfM and COLMAP undistortion raw-image-only

**Decision**: Record colour mode and relevant config in colour state, always use raw images for SfM feature extraction, matching, reconstruction, and COLMAP undistortion, and use completed mode-compatible restored outputs only for splatting-stage image inputs and user review.

**Rationale**: SfM geometry and undistortion must be reproducible from the original capture data. Colour restoration is an appearance transform for splatting, not a geometry or COLMAP undistortion input. Mode-aware state still prevents silent fallback and gives splat handoff code a concrete contract to inspect.

**Alternatives considered**:

- Trust any complete `recoloured_images/` tree: rejected because stale outputs from another mode can silently corrupt splatting inputs.
- Use restored images for COLMAP undistortion: rejected because SfM and undistortion must never consume colour-restored images.
- Delete incompatible outputs automatically: rejected because restored images are user data and output removal must be explicit.
