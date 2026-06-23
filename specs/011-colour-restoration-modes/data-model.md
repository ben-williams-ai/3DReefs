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

Enum controlling colour restoration and splatting image-source behaviour.

| Value | Meaning | Splat image source |
|-------|---------|-------------------------|
| `off` | Skip colour restoration entirely. | Raw images. |
| `gray_world` | Apply gray-world correction at full strength without GUI. | Completed restored images when safe. |
| `manual` | Use the existing GUI/keyframe workflow. | Completed restored images when safe. |

SfM feature extraction, matching, reconstruction, and COLMAP undistortion always use raw images for every mode.

## ColourRestorationState

Run-level state for manual or automatic restoration.

| Field | Purpose |
|-------|---------|
| `run_id` | Identifies the run that owns this state. |
| `status` | Tracks incomplete, active, applying, complete, skipped, cancelled, or failed lifecycle. |
| `active_session` | Blocks dependent splat work only for active/incomplete manual workflows. |
| `restoration_mode` | Records `gray_world` or `manual` so incompatible restored images cannot be reused across modes. |
| `source_raw_root` | Raw input image root, never modified in place. |
| `output_recoloured_root` | Restored image tree root for splatting/review only. |
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

Mirrored restored image tree used for splatting-stage image inputs and user review. It is never used for SfM or COLMAP undistortion.

| Property | Rule |
|----------|------|
| Relative paths | Must match the raw image tree exactly for expected dataset images. |
| Dimensions | Must match each source image. |
| Colour mode | Must be usable RGB output. |
| Ownership | Must be associated with the same run and compatible restoration mode before reuse. |
| Overwrite | May be regenerated only when `colour_restoration.overwrite` is `true`. |

## SfMImageSource

Raw image source used by COLMAP for all geometry and undistortion work.

| Property | Rule |
|----------|------|
| Source root | Always `raw_images/`, regardless of colour restoration mode. |
| Feature extraction | Always raw images. |
| Matching/reconstruction | Always raw images. |
| COLMAP undistortion | Always raw images. |
| Interaction with restored images | Restored images may be paired with raw-image geometry only at splatting input preparation time, outside SfM. |
