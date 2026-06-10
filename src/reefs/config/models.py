"""Typed configuration models for the pipeline foundation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResumePolicy(StrEnum):
    """Resume behaviour selected for this invocation."""

    PROMPT = "prompt"
    RESUME = "resume"
    OVERWRITE = "overwrite"
    FAIL = "fail"


class ProjectConfig(BaseModel):
    """Project-level settings."""

    model_config = ConfigDict(extra="forbid")

    dir: Path
    recolour_images: bool = False


class ToolsConfig(BaseModel):
    """External tool paths used for validation."""

    model_config = ConfigDict(extra="forbid")

    colmap_bin: str = "colmap"
    lfs_bin: str = "LichtFeld-Studio"
    splat_transform_bin: str = "splat-transform"


class PathsConfig(BaseModel):
    """Project-local path names, with relative values resolved under project.dir."""

    model_config = ConfigDict(extra="forbid")

    raw_images_dir: Path = Path("raw_images")
    recoloured_images_dir: Path = Path("recoloured_images")
    runs_dir: Path = Path("runs")


class LoggingConfig(BaseModel):
    """Run logging switches."""

    model_config = ConfigDict(extra="forbid")

    pipeline_log: bool = True
    warnings_log: bool = True


class ResumeConfig(BaseModel):
    """Persistent resume settings from config files."""

    model_config = ConfigDict(extra="forbid")

    mode: ResumePolicy = ResumePolicy.PROMPT
    compare_effective_config: bool = True
    require_decision_on_config_diff: bool = True


class SplatTrainConfig(BaseModel):
    """Future splat training settings recorded by Feature 1."""

    model_config = ConfigDict(extra="forbid")

    num_iters: int = Field(default=30000, gt=0)


class SogConfig(BaseModel):
    """Future SOG compression settings recorded by Feature 1."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class SplatConfig(BaseModel):
    """Future splatting settings recorded by Feature 1."""

    model_config = ConfigDict(extra="forbid")

    train: SplatTrainConfig = Field(default_factory=SplatTrainConfig)
    sog: SogConfig = Field(default_factory=SogConfig)


class PipelineConfig(BaseModel):
    """Complete typed pipeline configuration for Feature 1."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    resume: ResumeConfig = Field(default_factory=ResumeConfig)
    splat: SplatConfig = Field(default_factory=SplatConfig)

    @field_validator("project")
    @classmethod
    def project_dir_must_not_be_empty(cls, value: ProjectConfig) -> ProjectConfig:
        """Reject blank project paths."""
        if not str(value.dir):
            raise ValueError("project.dir is required")
        return value


class DerivedPaths(BaseModel):
    """Resolved project paths for one invocation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_dir: Path
    raw_images: Path
    recoloured_images: Path
    runs: Path


def model_to_plain_data(model: BaseModel) -> dict[str, Any]:
    """Serialise pydantic models into JSON/YAML-friendly dictionaries."""
    return model.model_dump(mode="json")
