"""Configuration loading and effective config helpers."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from reefs.config.models import PipelineConfig
from reefs.config.overrides import apply_overrides
from reefs.io.yaml_json import read_yaml


def load_config(path: Path) -> PipelineConfig:
    """Load and validate a pipeline config from YAML."""
    data = read_yaml(path)
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
