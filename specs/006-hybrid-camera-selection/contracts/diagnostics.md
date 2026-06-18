# Contract: Camera Selection Diagnostics

Each patch should write diagnostics under:

```text
splat/patches/<patch_id>/patch_diagnostics/
```

Required artefacts where diagnostic export succeeds:

```text
camera_coverage.csv
generation.log
plot.png
plot.html
histogram.png
```

`camera_coverage.csv` required columns:

```text
patch_id
image_id
image_name
selection_role
camera_role
candidate_source
selection_reason
rejection_reason
matched_track_score
geometric_visibility_score
target_image_share
new_target_sample_gain
view_direction_gain
camera_x
camera_y
camera_z
warning_flags
```

Rules:

- `camera_role` values are `internal` or `external`.
- `selection_role` distinguishes selected and unselected candidates.
- Plots must visually distinguish selected internal, rejected internal, selected
  external, and unused external cameras.
- Diagnostic failures are warnings if selected patch outputs remain valid.
- Diagnostics must not imply that buffer or edge regions were ranked as a
  separate privileged target.
