# Quickstart: Undistorted Colour Profiles

Create a profile locally:

```bash
uv run main.py colour profile create --config configs/dataset.yml --output profiles/dataset-colour.json
```

Use it headlessly:

```yaml
colour_restoration:
  mode: profile
  profile_path: profiles/dataset-colour.json
  overwrite: false
  start_sfm_immediately: true
```

Then resume the completed SfM run and request splatting. Confirm the manifest points training and evaluation at run-local corrected undistorted trees while sparse geometry remains under `sfm/`.
