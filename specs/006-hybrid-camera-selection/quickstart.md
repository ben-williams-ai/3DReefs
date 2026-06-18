# Quickstart: Camera Selection V2

Feature 006 is validated with patch diagnostics only. Do not launch LFS training
to accept this feature.

## 1. Run Unit And Integration Tests

```bash
uv run pytest -q tests/unit/test_patch_visibility.py tests/unit/test_patch_selection.py tests/unit/test_patch_selection_diagnostics.py tests/unit/test_patch_validation.py
```

## 2. Regenerate Patch Diagnostics For Known Reef Cases

Use an existing completed SfM run and run only patching:

```bash
uv run main.py \
  --config configs/datasets/dataset_01.yml \
  --run-id <diagnostic-run-id> \
  --steps splat.patch \
  --resume-policy overwrite \
  --advanced.splat.patching.max_cameras 800
```

Inspect:

```text
data/dataset1/runs/<diagnostic-run-id>/splat/patches/p002/patch_diagnostics/
```

Expected:

- no large unrepresented internal camera strip in `plot.png`
- selected camera count is within the configured cap
- useful internal and useful external cameras are visible in diagnostics

## 3. Compare Against The Known Failed Case

Generate or inspect the scratch side-by-side output for Dataset 1 patch800
`p002`:

```text
scratch/camera_selection_v2_comparison/dataset1_patch800_p002/
```

Expected:

- V2 keeps substantially more useful internal cameras than the failed selector
- V2 still allows useful external cameras
- no splat training is required

Record in the comparison summary:

- selected/rejected internal and external camera counts
- footprint coverage and target-image-share summaries
- selector runtime for the patch stage
- whether the diagnostic plot still shows an obvious unrepresented strip

## 4. Polish-Town Style Check

Run diagnostics on a representative oblique/vertical patch and inspect selected
external cameras.

Expected:

- useful external or oblique cameras remain selectable
- selected views are justified by footprint visibility or matched tracks
- target-image-share warnings identify sliver-heavy views
