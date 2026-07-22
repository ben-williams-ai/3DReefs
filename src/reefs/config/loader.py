"""Configuration loading and effective config helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from reefs.config.models import PipelineConfig
from reefs.config.overrides import apply_overrides
from reefs.io.yaml_json import read_yaml


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs from repo/local .env files if present."""
    for dotenv in [Path.cwd() / ".env", path.parent / ".env"]:
        if not dotenv.exists():
            continue
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _expand_env_values(value: Any) -> Any:
    """Recursively expand environment variables in YAML string values."""
    if isinstance(value, dict):
        return {key: _expand_env_values(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_expand_env_values(child) for child in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def load_config(path: Path) -> PipelineConfig:
    """Load and validate a pipeline config from YAML."""
    _load_dotenv(path)
    data = _expand_env_values(read_yaml(path))
    if isinstance(data, dict):
        if "colour_restoration" not in data:
            raise ValueError(
                "Config validation failed: missing required top-level colour_restoration block"
            )
        project = data.get("project")
        if isinstance(project, dict) and "recolour_images" in project:
            raise ValueError(
                "Config validation failed: project.recolour_images is no longer supported; "
                "use top-level colour_restoration.mode"
            )
        if isinstance(project, dict) and "start_sfm_immediately" in project:
            raise ValueError(
                "Config validation failed: project.start_sfm_immediately is no longer supported; "
                "use top-level colour_restoration.start_sfm_immediately"
            )
        colour = data.get("colour_restoration")
        if isinstance(colour, dict) and colour.get("profile_path"):
            profile_path = Path(str(colour["profile_path"]))
            if not profile_path.is_absolute():
                colour["profile_path"] = str((path.parent / profile_path).resolve())
    try:
        return PipelineConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Config validation failed: {exc}") from exc


def load_effective_config(
    path: Path, overrides: list[dict[str, object]] | None = None
) -> tuple[PipelineConfig, list[dict[str, object]]]:
    """Load a config and apply CLI overrides."""
    config = load_config(path)
    return apply_overrides(config, overrides or [])
