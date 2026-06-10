"""Partial-run discovery and resume decision helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reefs.io.yaml_json import read_json, read_yaml
from reefs.logging.timings import utc_now


@dataclass(frozen=True)
class PartialRun:
    """Prior run that requires user attention."""

    run_dir: Path
    step: str
    status: dict[str, Any] | None
    effective_config: dict[str, Any] | None
    manifest: dict[str, Any] | None
    reason: str


def discover_partial_runs(runs_dir: Path, requested_steps: list[str]) -> list[PartialRun]:
    """Find prior partial or uncertain runs for requested steps."""
    if not runs_dir.exists():
        return []
    partials: list[PartialRun] = []
    current_steps = set(requested_steps)
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        status_path = run_dir / "run_status.json"
        manifest_path = run_dir / "run_manifest.json"
        effective_path = run_dir / "effective_config.yml"
        status: dict[str, Any] | None = None
        manifest: dict[str, Any] | None = None
        effective: dict[str, Any] | None = None
        reason = ""
        try:
            status = read_json(status_path)
        except ValueError:
            reason = "missing_or_corrupt_status"
        try:
            manifest = read_json(manifest_path) if manifest_path.exists() else None
        except ValueError:
            reason = reason or "corrupt_manifest"
        try:
            effective = read_yaml(effective_path) if effective_path.exists() else None
        except ValueError:
            reason = reason or "corrupt_effective_config"

        previous_steps = set((manifest or {}).get("requested_steps") or ["foundation"])
        step_overlap = current_steps.intersection(previous_steps) or current_steps.intersection({"all"})
        if not step_overlap:
            continue
        status_value = str((status or {}).get("status", "unknown"))
        if status_value != "complete" or reason:
            for step in sorted(step_overlap):
                partials.append(
                    PartialRun(
                        run_dir=run_dir,
                        step=step,
                        status=status,
                        effective_config=effective,
                        manifest=manifest,
                        reason=reason or status_value,
                    )
                )
    return partials


def diff_effective_configs(previous: dict[str, Any] | None, requested: dict[str, Any]) -> list[dict[str, object]]:
    """Return shallow dotted-path config differences."""
    differences: list[dict[str, object]] = []

    def walk(prefix: str, left: Any, right: Any) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                child = f"{prefix}.{key}" if prefix else str(key)
                walk(child, left.get(key), right.get(key))
            return
        if left != right:
            differences.append(
                {
                    "path": prefix,
                    "previous_value": left,
                    "requested_value": right,
                    "source": "effective_config",
                }
            )

    walk("", previous or {}, requested)
    return differences


def build_config_diff_event(
    *, partial: PartialRun, requested_config: dict[str, Any], decision: str, interactive: bool
) -> dict[str, object] | None:
    """Build a config diff event if differences exist."""
    differences = diff_effective_configs(partial.effective_config, requested_config)
    if not differences:
        return None
    return {
        "previous_run_id": partial.run_dir.name,
        "detected_at": utc_now(),
        "differences": differences,
        "decision": decision,
        "interactive": interactive,
    }


def build_resume_event(*, partial: PartialRun, decision: str, source: str) -> dict[str, object]:
    """Build a serialisable resume event."""
    return {
        "step": partial.step,
        "previous_run_id": partial.run_dir.name,
        "previous_status": (partial.status or {}).get("status", "unknown"),
        "decision": decision,
        "source": source,
        "detected_at": utc_now(),
    }
