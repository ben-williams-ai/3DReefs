# Research: Splat Patching And Training

## Decision: Use pycolmap For Sparse Reconstruction Editing

**Rationale**: Feature 3 must read camera centres, sparse points, image tracks,
and write valid per-patch COLMAP sparse models. The old code used pycolmap for
this because it preserves COLMAP model semantics better than ad hoc text parsing
and binary rewriting.

**Alternatives considered**:
- Parse `cameras.txt`, `images.txt`, and `points3D.txt` manually: simpler
  dependency profile but fragile for subset export and track repair.
- Use only COLMAP CLI conversion commands: useful for binary/text conversion but
  not sufficient for view-based subset creation.

## Decision: Add matplotlib For Diagnostic Plots

**Rationale**: Outlier filtering and patching need top-down/side-on camera plots,
coverage histograms, and selection diagnostics. A headless plotting dependency
keeps these diagnostics reproducible and testable.

**Alternatives considered**:
- Hand-written SVG only: avoids dependency but increases maintenance burden for
  plots, legends, histograms, and future diagnostics.
- No plots: violates the requirement for inspectable patch/outlier diagnostics.

## Decision: Filter Into A Derived Reconstruction Copy

**Rationale**: The constitution and spec require data safety. Outlier filtering
changes which cameras/points are used downstream, so it should write a filtered
copy under the active run's `splat/outlier_filter/` area and leave Feature 2 SfM
outputs intact.

**Alternatives considered**:
- Modify selected sparse output in place: simpler but unsafe and hard to audit.
- Require users to duplicate runs manually: error-prone and contrary to one
  command/config operation.

## Decision: Treat Large Proposed Outlier Removal As Ambiguous

**Rationale**: Outliers are a small anomalous minority by definition. If many
cameras are flagged, the reconstruction may contain multiple clusters, real scene
movement, a poor SfM result, or an unsuitable threshold. The pipeline should stop
before patching rather than silently deleting much of the dataset.

**Alternatives considered**:
- Auto-remove all flagged cameras: dangerous for multi-cluster or valid movement.
- Auto-disable filtering: hides a major quality problem.
- Continue with warning: allows bad patch bounds to propagate into training.

## Decision: Use Birds-Eye Regions Only As Patch Anchors

**Rationale**: The user explicitly wants to move beyond the old birds-eye-only
patching. Camera-position regions are still useful for creating initial patch
anchors, but the final selected camera set should be chosen by view quality and
coverage of patch geometry.

**Alternatives considered**:
- Birds-eye-only selection: too crude for loop-heavy reef datasets.
- Dense point-cloud splitting: out of scope for the initial rebuild.
- Target-bin settings: explicitly rejected by the user.

## Decision: Use View-Based Camera Selection With Deterministic Scoring

**Rationale**: The old better-patching experiments scored cameras using local
and support views, visible sparse points, projected coverage, boundary coverage,
depth, and azimuth balancing. This provides a strong starting point while keeping
selection explainable through diagnostics.

**Alternatives considered**:
- Select only cameras whose centres fall inside a patch: misses useful support
  views looking into the patch.
- Select nearest cameras only: ignores actual visibility and coverage.
- Random or opaque selection: unacceptable for auditable research runs.

## Decision: Reuse Existing Patch Datasets For Training When Patch Inputs Match

**Rationale**: Patch generation may be expensive and diagnostics-heavy. If only
training parameters changed, reusing valid patches supports fast iteration while
preserving provenance. If patch-affecting settings changed, the user must decide
up front whether to regenerate or knowingly reuse.

**Alternatives considered**:
- Always regenerate: safe but wasteful for training ablations.
- Always reuse: unsafe when patch provenance changed.
- Never reuse across runs: too slow for experiments.

## Decision: Train Exactly One Patch At A Time

**Rationale**: For reef scenes the goal is to maximise patch size within GPU
capacity because larger patches tend to produce better outputs and fewer seams.
Running multiple LFS jobs concurrently would compete for VRAM and undermine that
goal. Independent small datasets can be run in separate commands by the user.

**Alternatives considered**:
- Auto-detect concurrency from GPU memory: complex and unreliable for LFS memory
  use.
- Configurable multi-patch concurrency: adds failure modes not needed for the
  intended workflow.

## Decision: Skip Invalid Requested Patches But Train Valid Ones

**Rationale**: A single invalid patch should not block useful training for other
valid patches, but all invalid patch decisions must be recorded before the first
LFS job starts so the batch remains unattended and auditable.

**Alternatives considered**:
- Fail the entire training stage: conservative but slows iteration when only one
  patch is bad.
- Prompt per invalid patch: violates the no mid-run prompt principle unless all
  prompts happen up front.

## Decision: Parse LFS Progress Into Patch Status Records

**Rationale**: The old code parsed progress lines containing completed
iterations, total iterations, loss, and splat count. Feature 3 should preserve
that value but write structured status JSON so the user does not need to parse
terminal output.

**Alternatives considered**:
- Trust process exit code only: insufficient because useful partial outputs can
  exist after non-zero exits.
- Require manual report inspection: too error-prone for many patch jobs.
