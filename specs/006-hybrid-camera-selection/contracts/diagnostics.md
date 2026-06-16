# Diagnostics Contract: Hybrid Camera Selection

## Required Per-Patch Diagnostics

Each generated patch should write:

```text
splat/patches/<patch_id>/patch_diagnostics/
  camera_coverage.csv
  plot.png
  plot.html
  histogram.png
  generation.log
```

Required content:
- selected local cameras
- rejected local cameras
- selected support/nonlocal cameras
- unused support/nonlocal cameras
- patch target bounds
- neighbouring patch context where available
- target/body coverage summary
- boundary coverage summary
- local camera-position cell coverage summary
- target-image-share or spillover warning summary
- view-direction diversity summary
- named warning thresholds used for meaningful target coverage, small target
  share, and excessive support/nonlocal use

Plot failures are non-critical only when `camera_coverage.csv`,
`generation.log`, patch metadata, selected images, and selected sparse export
remain valid.

## Required Run-Level Diagnostics

Patch generation should continue to write:

```text
splat/patches/patch_summary.png
```

Required content:
- all camera positions
- camera source colouring where source labels are available
- all generated patch rectangles

## Warning Semantics

Warnings must be visible in at least:
- `patch_metadata.json`
- `patch_diagnostics/generation.log`
- Feature 1 run warnings/status records

Warning examples:
- poor selector coverage
- weak boundary coverage
- weak local camera-position coverage
- high support/nonlocal fraction
- high spillover risk
- non-critical diagnostic plot export failure

Warnings do not block training by default when patch inputs and generated patch
artefacts are valid.
