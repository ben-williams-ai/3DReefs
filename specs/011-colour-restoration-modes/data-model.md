# Data Model: Colour Restoration Modes

## ColourRestorationConfig

Represents the required top-level config block.

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `mode` | `ColourRestorationMode` | `off` | Must be `off`, `gray_world`, or `manual`. |
| `overwrite` | `bool` | `false` | Controls same-run restored image reuse/regeneration for `gray_world` and `manual`. |
| `start_sfm_immediately` | `bool` | `true` | Applies only to `manual`; ignored by `off` and `gray_world`. |

### Relationships

- Belongs to the root pipeline config, not `project`.
- Replaces legacy `project.recolour_images` and `project.start_sfm_immediately`.
- Values are recorded in effective config and relevant colour state/manifest metadata.

## ColourRestorationMode

Enum controlling image source behaviour.

| Value | Meaning | Downstream image source |
|-------|---------|-------------------------|
| `off` | Skip colour restoration entirely. | Raw images. |
| `gray_world` | Apply gray-world correction at full strength without GUI. | Completed restored images. |
| `manual` | Use the existing GUI/keyframe workflow. | Completed restored images when safe. |

## ColourRestorationState

Run-level state for manual or automatic restoration.

| Field | Purpose |
|-------|---------|
| `run_id` | Identifies the run that owns this state. |
| `status` | Tracks incomplete, active, applying, complete, skipped, cancelled, or failed lifecycle. |
| `active_session` | Blocks dependent splat work only for active/incomplete manual workflows. |
| `restoration_mode` | Records `gray_world` or `manual` so incompatible restored images cannot be reused across modes. |
| `source_raw_root` | Raw input image root, never modified in place. |
| `output_recoloured_root` | Restored image tree root. |
| `relevant_config` | Records mode, overwrite, start-SfM behaviour, and adoption/regeneration decisions. |
| `interpolation` | Existing manual interpolation details or automatic gray-world application metadata. |

### State Transitions

```text
off
└── no colour state required

gray_world
└── applying -> complete
    applying -> failed
    complete + overwrite:false -> complete (reuse)
    complete + overwrite:true -> applying -> complete

manual
└── incomplete -> active -> applying -> complete
    incomplete/active/applying -> failed|cancelled
    complete + overwrite:false -> complete (reuse when safe)
    complete + overwrite:true -> active/applying -> complete
```

## RestoredImageSet

Mirrored restored image tree used for downstream undistortion.

| Property | Rule |
|----------|------|
| Relative paths | Must match the raw image tree exactly for expected dataset images. |
| Dimensions | Must match each source image. |
| Colour mode | Must be usable RGB output. |
| Ownership | Must be associated with the same run and compatible restoration mode before reuse. |
| Overwrite | May be regenerated only when `colour_restoration.overwrite` is `true`. |
