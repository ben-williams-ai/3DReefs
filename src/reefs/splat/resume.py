"""Existing patch and training output decision helpers."""

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
from reefs.patches.selection import selector_settings
from reefs.splat.validation import SplatPaths, expand_splat_steps


@dataclass(frozen=True)
class ExistingSplatOutput:
    """Prior splat output that needs a decision before work starts."""

    stage: str
    path: Path
    state: str
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable output record."""
        return {
            "stage": self.stage,
            "path": str(self.path),
            "state": self.state,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SplatOutputDecision:
    """Decision for an existing splat output."""

    output: ExistingSplatOutput
    decision: str
    source: str
    decided_at: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable decision record."""
        return {
            **self.output.as_dict(),
            "decision": self.decision,
            "source": self.source,
            "decided_at": self.decided_at,
        }


def _directory_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    if any(path.iterdir()):
        return "present"
    return "empty"


def discover_existing_splat_outputs(paths: SplatPaths, requested_steps: list[str]) -> list[ExistingSplatOutput]:
    """Find existing splat outputs for requested stages."""
    requested = set(expand_splat_steps(requested_steps))
    run_all = "splat" in requested_steps
    outputs: list[ExistingSplatOutput] = []
    if run_all or "splat.outlier_filter" in requested:
        state = _directory_state(paths.outlier_filter)
        if state == "present":
            outputs.append(
                ExistingSplatOutput(
                    stage="splat.outlier_filter",
                    path=paths.outlier_filter,
                    state=state,
                    reason="existing_outlier_filter_output",
                )
            )
    if run_all or "splat.patch" in requested:
        state = _directory_state(paths.patches)
        if state == "present":
            outputs.append(
                ExistingSplatOutput(
                    stage="splat.patch",
                    path=paths.patches,
                    state=state,
                    reason="existing_patch_output",
                )
            )
    if run_all or "splat.train" in requested:
        patch_splat_dirs = sorted(paths.patches.glob("*/splat")) if paths.patches.exists() else []
        for patch_splat in patch_splat_dirs:
            state = _directory_state(patch_splat)
            if state == "present":
                outputs.append(
                    ExistingSplatOutput(
                        stage="splat.train",
                        path=patch_splat,
                        state=state,
                        reason="existing_training_output",
                    )
                )
    return outputs


def resolve_existing_splat_outputs(
    *,
    existing_outputs: list[ExistingSplatOutput],
    resume_policy: ResumePolicy,
) -> list[SplatOutputDecision]:
    """Resolve existing splat outputs before any splat work starts."""
    if not existing_outputs:
        return []
    interactive = sys.stdin.isatty()
    if resume_policy == ResumePolicy.FAIL:
        raise ValueError("Existing splat outputs require a resume or overwrite decision")
    if resume_policy == ResumePolicy.PROMPT and not interactive:
        raise ValueError(
            "Existing splat outputs detected in a non-interactive run. "
            "Supply --resume-policy resume, overwrite, or fail."
        )

    decisions: list[SplatOutputDecision] = []
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
            SplatOutputDecision(
                output=output,
                decision=decision,
                source=source,
                decided_at=utc_now(),
            )
        )
    return decisions


def apply_overwrite_decisions(decisions: list[SplatOutputDecision]) -> list[dict[str, object]]:
    """Delete existing output directories selected for overwrite."""
    events: list[dict[str, object]] = []
    for item in decisions:
        if item.decision != "overwrite":
            continue
        path = item.output.path
        if path.exists():
            shutil.rmtree(path)
            events.append(
                {
                    "stage": item.output.stage,
                    "action": "deleted_existing_output",
                    "path": str(path),
                    "detected_at": item.decided_at,
                }
            )
    return events


def materialise_patch_affecting_config(config) -> dict[str, object]:
    """Return settings that affect patch generation/reuse."""
    return {
        "outlier_filter": config.advanced.splat.outlier_filter.model_dump(mode="json"),
        "patching": config.advanced.splat.patching.model_dump(mode="json"),
        "selector": selector_settings(),
    }


def diff_patch_affecting_config(previous: Any, requested: dict[str, object]) -> list[dict[str, object]]:
    """Return dotted-path differences for patch-affecting config values."""
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


def inspect_patch_affecting_config_changes(paths: SplatPaths, config) -> list[dict[str, object]]:
    """Inspect existing patch metadata for patch-affecting config changes."""
    requested = materialise_patch_affecting_config(config)
    changes: list[dict[str, object]] = []
    if not paths.patches.exists():
        return changes
    for metadata_path in sorted(paths.patches.glob("*/patch_metadata.json")):
        try:
            metadata = read_json(metadata_path)
        except ValueError:
            continue
        if not isinstance(metadata, dict):
            continue
        patch_id = str(metadata.get("patch_id", metadata_path.parent.name))
        differences = diff_patch_affecting_config(metadata.get("patch_affecting_config"), requested)
        if differences:
            changes.append(
                {
                    "patch_id": patch_id,
                    "metadata_path": str(metadata_path),
                    "differences": differences,
                }
            )
    return changes
