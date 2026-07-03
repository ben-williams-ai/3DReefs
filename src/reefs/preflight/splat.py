"""Splat-stage preflight validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from reefs.colour.pipeline import colour_state_path
from reefs.colour.state import maybe_load_state, state_allows_splat
from reefs.config.models import ColourRestorationMode
from reefs.config.models import ResumePolicy
from reefs.postprocess.cleanup import validate_cleanup_backend
from reefs.postprocess.resume import (
    ExistingPostprocessOutput,
    PostprocessOutputDecision,
    discover_existing_postprocess_outputs,
    inspect_postprocess_config_changes,
    postprocess_stages,
    resolve_postprocess_outputs,
    wants_postprocess,
)
from reefs.patches.bounds import validate_patch_bounds_backend
from reefs.preflight.tools import validate_splat_transform
from reefs.splat.resume import (
    ExistingSplatOutput,
    SplatOutputDecision,
    discover_existing_splat_outputs,
    inspect_patch_affecting_config_changes,
    resolve_existing_splat_outputs,
)
from reefs.splat.validation import (
    SplatPaths,
    SplatSourceValidation,
    create_splat_paths,
    expand_splat_steps,
    validate_pycolmap_available,
    validate_splat_source,
    wants_splat_training,
)


@dataclass(frozen=True)
class SplatPreflightResult:
    """Validated Feature 3 preflight data."""

    source: SplatSourceValidation
    paths: SplatPaths
    existing_outputs: list[ExistingSplatOutput] = field(default_factory=list)
    output_decisions: list[SplatOutputDecision] = field(default_factory=list)
    postprocess_existing_outputs: list[ExistingPostprocessOutput] = field(default_factory=list)
    postprocess_output_decisions: list[PostprocessOutputDecision] = field(default_factory=list)
    patch_affecting_config_changes: list[dict[str, object]] = field(default_factory=list)
    postprocess_config_changes: list[dict[str, object]] = field(default_factory=list)
    tool_results: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable preflight result."""
        return {
            "source": self.source.as_dict(),
            "paths": {
                "root": str(self.paths.root),
                "outlier_filter": str(self.paths.outlier_filter),
                "filtered_sparse": str(self.paths.filtered_sparse),
                "patches": str(self.paths.patches),
                "training": str(self.paths.training),
                "postprocess": str(self.paths.postprocess),
                "postprocess_manifest": str(self.paths.postprocess_manifest),
                "merged": str(self.paths.merged),
                "merged_ply": str(self.paths.merged_ply),
                "sog": str(self.paths.sog),
                "final_sog": str(self.paths.final_sog),
                "lfs_log": str(self.paths.lfs_log),
                "splat_transform_log": str(self.paths.splat_transform_log),
            },
            "existing_outputs": [output.as_dict() for output in self.existing_outputs],
            "output_decisions": [decision.as_dict() for decision in self.output_decisions],
            "postprocess_existing_outputs": [output.as_dict() for output in self.postprocess_existing_outputs],
            "postprocess_output_decisions": [decision.as_dict() for decision in self.postprocess_output_decisions],
            "patch_affecting_config_changes": self.patch_affecting_config_changes,
            "postprocess_config_changes": self.postprocess_config_changes,
            "tool_results": self.tool_results,
            "warnings": self.warnings,
        }


def validate_splat_preflight(
    *,
    config,
    run_paths,
    requested_steps: list[str],
    resume_policy: ResumePolicy,
) -> SplatPreflightResult:
    """Validate all splat prerequisites that can be checked up front."""
    if config.colour_restoration.mode == ColourRestorationMode.MANUAL:
        state = maybe_load_state(colour_state_path(run_paths.run_dir))
        if state is None or not state_allows_splat(state):
            raise ValueError(
                "Colour restoration is not complete or a colour session is active; splatting is waiting for colour restoration"
            )
    validate_pycolmap_available()
    source = validate_splat_source(run_paths, config=config)
    paths = create_splat_paths(run_paths)
    existing = discover_existing_splat_outputs(
        paths,
        requested_steps,
        train_patch_ids=config.advanced.splat.train.patch_ids,
    )
    postprocess_existing = discover_existing_postprocess_outputs(paths=paths, requested_steps=requested_steps)
    patch_config_changes = inspect_patch_affecting_config_changes(paths, config)
    postprocess_config_changes = inspect_postprocess_config_changes(paths, config)
    if patch_config_changes and resume_policy == ResumePolicy.RESUME:
        changed = ", ".join(str(item["patch_id"]) for item in patch_config_changes[:10])
        raise ValueError(
            "Patch-affecting config changed for existing patches "
            f"({changed}). Use --resume-policy overwrite to regenerate patches."
        )
    if postprocess_config_changes and resume_policy == ResumePolicy.RESUME:
        raise ValueError(
            "Post-processing config changed for existing outputs. "
            "Use --resume-policy overwrite to regenerate post-processing outputs."
        )
    decisions = resolve_existing_splat_outputs(existing_outputs=existing, resume_policy=resume_policy)
    postprocess_decisions = resolve_postprocess_outputs(
        existing_outputs=postprocess_existing,
        resume_policy=resume_policy,
    )
    warnings = list(source.warnings)
    for change in patch_config_changes:
        warnings.append(f"Patch-affecting config differs for {change['patch_id']}; decision required before reuse.")
    for change in postprocess_config_changes:
        warnings.append(f"Post-processing config differs for {change['manifest']}; decision required before reuse.")
    if wants_splat_training(requested_steps) and not config.tools.lfs_bin:
        raise ValueError("splat.train/splat.eval requires tools.lfs_bin")
    tool_results: list[dict[str, object]] = []
    expanded_steps = set(expand_splat_steps(requested_steps))
    if "splat.patch" in expanded_steps:
        patch_validation = validate_patch_bounds_backend()
        tool_results.append(patch_validation.as_dict())
        if patch_validation.status != "passed":
            raise ValueError(patch_validation.message)
    stages = postprocess_stages(requested_steps)
    if wants_postprocess(requested_steps):
        cleanup_validation = validate_cleanup_backend(config.advanced.splat.cleanup)
        tool_results.append(cleanup_validation.as_dict())
        if cleanup_validation.status != "passed" and "splat.cleanup" in stages:
            raise ValueError(cleanup_validation.message)
        if "splat.merge" in stages and cleanup_validation.status != "passed":
            raise ValueError(cleanup_validation.message)
        if "splat.sog" in stages:
            transform_validation = validate_splat_transform(
                config.tools.splat_transform_bin,
                require_sog=True,
            )
            tool_results.append(transform_validation.as_dict())
            if transform_validation.status != "passed":
                raise ValueError(transform_validation.message)
    return SplatPreflightResult(
        source=source,
        paths=paths,
        existing_outputs=existing,
        output_decisions=decisions,
        postprocess_existing_outputs=postprocess_existing,
        postprocess_output_decisions=postprocess_decisions,
        patch_affecting_config_changes=patch_config_changes,
        postprocess_config_changes=postprocess_config_changes,
        tool_results=tool_results,
        warnings=warnings,
    )
