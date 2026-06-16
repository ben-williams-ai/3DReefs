# Run Record Contract: Splat Cleanup And SOG Compression

Feature 5 extends existing Feature 1 run records. It must not create duplicate markdown reports for the same information.

## Stage Names

Use these stage identifiers in status and timing records:

- `splat.cleanup`
- `splat.cleanup.<patch_id>`
- `splat.merge`
- `splat.sog`
- `splat.postprocess`

`splat.postprocess` is a summary stage that covers cleanup, merge, and SOG when requested as a full sequence.

## run_status.json Additions

`run_status.json` must expose enough information for resume:

```json
{
  "current_stage": "splat.cleanup.p000",
  "last_completed_stage": "splat.cleanup.p000",
  "stages": {
    "splat.cleanup": {
      "status": "running",
      "started_at": "<ISO8601>",
      "updated_at": "<ISO8601>"
    },
    "splat.merge": {
      "status": "pending"
    },
    "splat.sog": {
      "status": "pending"
    }
  }
}
```

Completed full post-processing must not be reported until cleanup, merge, and requested SOG export have all completed or been explicitly reused.

## timings.json Additions

Timings must include:

- one entry for each cleaned patch that actually runs
- one entry for `splat.merge` when merge runs
- one entry for `splat.sog` when SOG export runs
- skipped/reused entries may include zero duration plus the decision reason

## Post-Processing Manifest Summary

`splat/postprocess/postprocess_manifest.json` is the source of truth for post-processing-specific details. `run_manifest.json` should reference it rather than duplicating every per-patch field.

Minimum `run_manifest.json` addition:

```json
{
  "postprocess": {
    "manifest": "splat/postprocess/postprocess_manifest.json",
    "merged_ply": "splat/merged/merged_splat.ply",
    "sog": "splat/merged/merged_splat.sog",
    "status": "partial"
  }
}
```

## Warning Requirements

The warning summary must prominently include:

- patches excluded from merge
- patches included from incomplete training sources
- any severe incomplete sources below 80 percent of requested iterations
- missing or unavailable wildflow cleanup/merge functionality
- missing or unsupported `splat-transform` for final SOG
- failed SOG export after valid merge

## Resume Requirements

Before work starts, resume detection must inspect both structured records and filesystem outputs:

- existing cleaned patch PLYs
- existing merged cleaned PLY
- existing final SOG
- previous post-processing manifest when present

Existing outputs must be resolved by explicit `resume`, `overwrite`, or `fail` policy before cleanup, merge, or SOG starts.
