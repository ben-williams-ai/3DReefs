"""Resume and overwrite helpers for splat post-processing outputs."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from reefs.config.models import ResumePolicy
from reefs.io.yaml_json import read_json
from reefs.logging.timings import utc_now
from reefs.splat.validation import SplatPaths, expand_splat_steps


@dataclass(frozen=True)
class ExistingPostprocessOutput:
    """Prior post-processing output that needs an up-front decision."""

    stage: str
    path: Path
    state: str
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable record."""
        return {
            "stage": self.stage,
            "path": str(self.path),
            "state": self.state,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PostprocessOutputDecision:
    """Decision for an existing post-processing output."""

    output: ExistingPostprocessOutput
    decision: str
    source: str
    decided_at: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable decision."""
        return {
            **self.output.as_dict(),
            "decision": self.decision,
            "source": self.source,
            "decided_at": self.decided_at,
        }


def wants_postprocess(requested_steps: list[str]) -> bool:
    """Return whether requested steps include cleanup, merge, or SOG."""
    expanded = set(expand_splat_steps(requested_steps))
    return bool(expanded & {"splat.cleanup", "splat.merge", "splat.sog"})


def postprocess_stages(requested_steps: list[str]) -> list[str]:
    """Return requested post-processing stages in execution order."""
    expanded = set(expand_splat_steps(requested_steps))
    return [stage for stage in ["splat.cleanup", "splat.merge", "splat.sog"] if stage in expanded]


def _state(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_dir():
        return "present" if any(path.iterdir()) else "empty"
    return "present" if path.stat().st_size > 0 else "empty"


def discover_existing_postprocess_outputs(
    *,
    paths: SplatPaths,
    requested_steps: list[str],
) -> list[ExistingPostprocessOutput]:
    """Find existing cleanup, merge, and SOG outputs for requested stages."""
    stages = set(postprocess_stages(requested_steps))
    outputs: list[ExistingPostprocessOutput] = []
    if "splat.cleanup" in stages and paths.patches.exists():
        for cleaned in sorted(paths.patches.glob("*/splat/*_clean.ply")):
            if _state(cleaned) == "present":
                outputs.append(
                    ExistingPostprocessOutput(
                        stage="splat.cleanup",
                        path=cleaned,
                        state="present",
                        reason="existing_cleaned_patch_output",
                    )
                )
    if "splat.merge" in stages and _state(paths.merged_ply) == "present":
        outputs.append(
            ExistingPostprocessOutput(
                stage="splat.merge",
                path=paths.merged_ply,
                state="present",
                reason="existing_merged_site_splat",
            )
        )
    if "splat.sog" in stages and _state(paths.final_sog) == "present":
        outputs.append(
            ExistingPostprocessOutput(
                stage="splat.sog",
                path=paths.final_sog,
                state="present",
                reason="existing_final_sog",
            )
        )
    return outputs


def resolve_postprocess_outputs(
    *,
    existing_outputs: list[ExistingPostprocessOutput],
    resume_policy: ResumePolicy,
) -> list[PostprocessOutputDecision]:
    """Resolve existing post-processing outputs before any work starts."""
    if not existing_outputs:
        return []
    interactive = sys.stdin.isatty()
    if resume_policy == ResumePolicy.FAIL:
        raise ValueError("Existing post-processing outputs require a resume or overwrite decision")
    if resume_policy == ResumePolicy.PROMPT and not interactive:
        raise ValueError(
            "Existing post-processing outputs detected in a non-interactive run. "
            "Supply --resume-policy resume, overwrite, or fail."
        )
    decisions: list[PostprocessOutputDecision] = []
    for output in existing_outputs:
        if resume_policy == ResumePolicy.RESUME:
            decision = "reuse"
            source = "resume_policy"
        elif resume_policy == ResumePolicy.OVERWRITE:
            decision = "overwrite"
            source = "resume_policy"
        else:
            message = f"Existing output for {output.stage} found at {output.path}. Reuse it?"
            decision = "reuse" if click.confirm(message, default=False) else "overwrite"
            source = "interactive_prompt"
        decisions.append(
            PostprocessOutputDecision(
                output=output,
                decision=decision,
                source=source,
                decided_at=utc_now(),
            )
        )
    return decisions


def apply_postprocess_overwrite_decisions(decisions: list[PostprocessOutputDecision]) -> list[dict[str, object]]:
    """Delete existing generated post-processing outputs selected for overwrite."""
    events: list[dict[str, object]] = []
    for item in decisions:
        if item.decision != "overwrite":
            continue
        path = item.output.path
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
        events.append(
            {
                "stage": item.output.stage,
                "action": "deleted_existing_output",
                "path": str(path),
                "detected_at": item.decided_at,
            }
        )
    return events


def materialise_postprocess_config(config) -> dict[str, object]:
    """Return post-processing settings that affect output reuse."""
    splat = config.advanced.splat
    return {
        "cleanup": splat.cleanup.model_dump(mode="json"),
        "merge": splat.merge.model_dump(mode="json"),
        "sog": splat.sog.model_dump(mode="json"),
    }


def diff_postprocess_config(previous: Any, requested: dict[str, object]) -> list[dict[str, object]]:
    """Return dotted-path differences for post-processing settings."""
    differences: list[dict[str, object]] = []

    def walk(prefix: str, left: Any, right: Any) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                walk(f"{prefix}.{key}" if prefix else str(key), left.get(key), right.get(key))
            return
        if left != right:
            differences.append({"path": prefix, "previous_value": left, "requested_value": right})

    walk("", previous or {}, requested)
    return differences


def inspect_postprocess_config_changes(paths: SplatPaths, config) -> list[dict[str, object]]:
    """Compare previous post-processing manifest settings with requested settings."""
    manifest_path = paths.postprocess_manifest
    if not manifest_path.exists():
        return []
    try:
        manifest = read_json(manifest_path)
    except ValueError:
        return []
    if not isinstance(manifest, dict):
        return []
    differences = diff_postprocess_config(manifest.get("effective_settings"), materialise_postprocess_config(config))
    if not differences:
        return []
    return [{"manifest": str(manifest_path), "differences": differences}]
