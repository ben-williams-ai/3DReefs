# Run Record Contract: Hybrid Camera Selection

Feature 006 uses the existing Feature 1 run-record system and Feature 3 patch
stage names.

## Stage Status

The patching stage records must include:
- `splat.patch` status
- started, updated, and ended timestamps
- selector name and version
- selector-affecting signature
- named selector warning thresholds
- per-patch status: `complete_valid`, `complete_with_warnings`, `failed`, or
  `reused`
- coverage warnings by patch
- reuse/overwrite decisions for incompatible existing outputs

## Timings

Timings must separate:
- patch target construction
- candidate discovery
- camera scoring
- greedy selection
- sparse export
- diagnostic export

Small implementations may aggregate target construction and camera scoring in a
single per-patch selector timing, but the run record must still make selector
time distinguishable from LFS training time.

## Resume And Overwrite

Selector-affecting changes include:
- selector name or version
- patch bounds
- selected source sparse model
- `patching.max_cameras`
- target sample settings
- density weighting settings
- selection scoring weights
- view-bin settings
- target-image-share penalty settings

When existing patch outputs were generated with incompatible selector-affecting
settings, the run must require an up-front reuse or overwrite decision before
any requested patch work starts.
