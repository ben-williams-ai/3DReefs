"""Typed configuration models for the pipeline foundation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

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
    vocab_tree_path: Path | None = None


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


class SplatOutlierFilterConfig(BaseModel):
    """Camera pose outlier filtering settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    dry_run: bool = False
    max_removal_fraction: float = Field(default=0.05, ge=0.0, le=1.0)
    method: Literal["iqr", "percentile"] = "iqr"
    iqr_mult: float = Field(default=3.0, gt=0.0)
    percentile: float = Field(default=99.9, gt=50.0, lt=100.0)


def _parse_patch_ids(value: Any) -> list[str] | None:
    """Parse optional patch id lists from YAML lists or simple CLI strings."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in {"", "none", "null"}:
            return None
        if stripped.startswith("[") and stripped.endswith("]"):
            stripped = stripped[1:-1]
        return [item.strip().strip("\"'") for item in stripped.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("patch_ids must be null, a list, or a bracketed CLI string")


class SplatPatchingConfig(BaseModel):
    """Patch generation settings."""

    model_config = ConfigDict(extra="forbid")

    max_cameras: int = Field(default=800, gt=0)
    buffer: float = Field(default=0.1, ge=0.0)
    mode: Literal["view_based"] = "view_based"
    run_interactive_patch_visualiser: bool = False
    patch_ids: list[str] | None = None

    @field_validator("patch_ids", mode="before")
    @classmethod
    def parse_patch_ids(cls, value: Any) -> list[str] | None:
        """Accept CLI-friendly patch id lists."""
        return _parse_patch_ids(value)


class SplatTrainConfig(BaseModel):
    """LFS patch training settings."""

    model_config = ConfigDict(extra="forbid")

    num_iters: int = Field(default=30000, gt=0)
    num_splats_per_patch: int = Field(default=1_500_000, gt=0)
    strategy: str = "mcmc"
    headless: bool = True
    patch_ids: list[str] | None = None
    retrain_failed: bool = False
    severe_completion_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    lfs_config: Path | None = None

    @field_validator("patch_ids", mode="before")
    @classmethod
    def parse_patch_ids(cls, value: Any) -> list[str] | None:
        """Accept CLI-friendly patch id lists."""
        return _parse_patch_ids(value)


class SplatCleanupConfig(BaseModel):
    """Post-training splat cleanup settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    max_area: float = Field(default=0.004, gt=0.0)
    min_neighbors: int = Field(default=20, ge=0)
    radius: float = Field(default=0.05, gt=0.0)
    filter_boundaries: bool = True
    boundary_buffer: float = Field(default=0.1, ge=0.0)
    patch_ids: list[str] | None = None

    @field_validator("patch_ids", mode="before")
    @classmethod
    def parse_patch_ids(cls, value: Any) -> list[str] | None:
        """Accept CLI-friendly patch id lists."""
        return _parse_patch_ids(value)


class SplatMergeConfig(BaseModel):
    """Cleaned patch merge settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    require_cleaned: bool = True
    continue_with_available: bool = True
    output_name: str = "merged_splat.ply"
    patch_ids: list[str] | None = None

    @field_validator("patch_ids", mode="before")
    @classmethod
    def parse_patch_ids(cls, value: Any) -> list[str] | None:
        """Accept CLI-friendly patch id lists."""
        return _parse_patch_ids(value)


class SogConfig(BaseModel):
    """Final SOG compression settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    source: Literal["merged"] = "merged"
    output_name: str = "merged_splat.sog"
    filter_nan: bool = True
    filter_harmonics: int = Field(default=2, ge=0, le=3)
    iterations: int | None = Field(default=None, gt=0)


class SplatConfig(BaseModel):
    """Advanced splatting settings."""

    model_config = ConfigDict(extra="forbid")

    outlier_filter: SplatOutlierFilterConfig = Field(default_factory=SplatOutlierFilterConfig)
    patching: SplatPatchingConfig = Field(default_factory=SplatPatchingConfig)
    train: SplatTrainConfig = Field(default_factory=SplatTrainConfig)
    cleanup: SplatCleanupConfig = Field(default_factory=SplatCleanupConfig)
    merge: SplatMergeConfig = Field(default_factory=SplatMergeConfig)
    sog: SogConfig = Field(default_factory=SogConfig)


class CameraConfig(BaseModel):
    """SfM camera layout settings."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["auto", "single", "multi"] = "auto"
    camera_mapping: dict[str, str] | None = None


class SfMPreflightConfig(BaseModel):
    """SfM-specific preflight switches."""

    model_config = ConfigDict(extra="forbid")

    check_dimensions: bool = True
    check_camera_source_metadata: bool = True
    proceed_on_mixed_camera_sources: bool = False
    exif_pose_priors_enabled: bool = False
    validate_gpu_support: bool = True


class IntrinsicsRefineConfig(BaseModel):
    """Final reconstruction intrinsics refinement switches."""

    model_config = ConfigDict(extra="forbid")

    focal_length: bool = False
    principal_point: bool = False
    extra_params: bool = False


class IntrinsicsConfig(BaseModel):
    """SfM intrinsics settings."""

    model_config = ConfigDict(extra="forbid")

    camera_model: str = "OPENCV"
    precalculate: bool = True
    cameras_txt: Path | None = None
    selection_start_index: int = Field(default=50, ge=0)
    selection_end_index: int = Field(default=150, ge=1)
    preferred_min_images: int = Field(default=100, ge=1)
    refine: IntrinsicsRefineConfig = Field(default_factory=IntrinsicsRefineConfig)


class SiftExtractionConfig(BaseModel):
    """COLMAP SIFT extraction settings."""

    model_config = ConfigDict(extra="forbid")

    first_octave: int = -1
    num_octaves: int = Field(default=4, gt=0)
    octave_resolution: int = Field(default=3, gt=0)
    peak_threshold: float = Field(default=0.00667, gt=0)
    edge_threshold: float = Field(default=10.0, gt=0)
    max_num_orientations: int = Field(default=2, gt=0)
    estimate_affine_shape: bool = False
    upright: bool = False


class FeatureExtractionConfig(BaseModel):
    """COLMAP feature extraction settings."""

    model_config = ConfigDict(extra="forbid")

    max_image_size: int | None = Field(default=None, gt=0)
    max_num_features: int = Field(default=8192, gt=0)
    use_gpu: bool = True
    gpu_index: int = -1
    sift: SiftExtractionConfig = Field(default_factory=SiftExtractionConfig)


class LoopDetectionConfig(BaseModel):
    """COLMAP sequential matcher loop detection settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    period: int = Field(default=10, gt=0)
    num_images: int = Field(default=100, gt=0)
    num_nearest_neighbors: int = Field(default=1, gt=0)
    num_checks: int = Field(default=64, gt=0)


class SequentialMatchingConfig(BaseModel):
    """COLMAP sequential matching settings."""

    model_config = ConfigDict(extra="forbid")

    overlap: int = Field(default=15, gt=0)
    quadratic_overlap: bool = True
    loop_detection: LoopDetectionConfig = Field(default_factory=LoopDetectionConfig)


class VocabTreeMatchingConfig(BaseModel):
    """COLMAP vocabulary-tree matching settings."""

    model_config = ConfigDict(extra="forbid")

    num_images: int = Field(default=150, gt=0)
    num_nearest_neighbors: int = Field(default=5, gt=0)
    num_checks: int = Field(default=64, gt=0)


class SpatialMatchingConfig(BaseModel):
    """COLMAP spatial matching settings."""

    model_config = ConfigDict(extra="forbid")

    max_num_neighbors: int | None = Field(default=None, gt=0)
    min_num_neighbors: int | None = Field(default=None, ge=0)
    ignore_z: bool = True
    max_distance: float | None = Field(default=None, gt=0)


class MatchingConfig(BaseModel):
    """COLMAP image matching settings."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal[
        "exhaustive",
        "sequential",
        "vocab_tree",
        "spatial",
        "sequential_vocab_tree",
        "hybrid",
    ] = "sequential_vocab_tree"
    use_gpu: bool = True
    gpu_index: int = -1
    sequential: SequentialMatchingConfig = Field(default_factory=SequentialMatchingConfig)
    vocab_tree: VocabTreeMatchingConfig = Field(default_factory=VocabTreeMatchingConfig)
    spatial: SpatialMatchingConfig = Field(default_factory=SpatialMatchingConfig)


class ReconstructionConfig(BaseModel):
    """COLMAP sparse reconstruction settings."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["global", "incremental"] = "global"
    validate_backend: bool = True
    use_gpu: bool = True
    options: dict[str, Any] | None = None


class UndistortionConfig(BaseModel):
    """COLMAP undistortion settings."""

    model_config = ConfigDict(extra="forbid")

    max_image_size: int = Field(default=4096, gt=0)
    image_source: Literal["auto", "raw", "recoloured"] = "auto"


class PatchMatchConfig(BaseModel):
    """Optional dense patch-match settings."""

    model_config = ConfigDict(extra="forbid")

    max_image_size: int = Field(default=2000, gt=0)
    geom_consistency: bool = True


class FusionConfig(BaseModel):
    """Optional dense fusion settings."""

    model_config = ConfigDict(extra="forbid")

    min_num_pixels: int = Field(default=5, gt=0)
    max_reproj_error: float = Field(default=2.0, gt=0)
    max_depth_error: float = Field(default=0.01, gt=0)
    max_normal_error: float = Field(default=10.0, gt=0)


class MeshConfig(BaseModel):
    """Optional mesh settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    poisson_depth: int = Field(default=13, gt=0)


class DenseConfig(BaseModel):
    """Optional dense reconstruction settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    patch_match: PatchMatchConfig = Field(default_factory=PatchMatchConfig)
    fusion: FusionConfig = Field(default_factory=FusionConfig)
    mesh: MeshConfig = Field(default_factory=MeshConfig)

    @field_validator("mesh")
    @classmethod
    def mesh_requires_dense(cls, value: MeshConfig, info) -> MeshConfig:
        """Reject mesh-only dense configuration."""
        if value.enabled and not info.data.get("enabled", False):
            raise ValueError("advanced.sfm.dense.mesh.enabled requires advanced.sfm.dense.enabled")
        return value


class SfMConfig(BaseModel):
    """Advanced settings for the COLMAP SfM pipeline."""

    model_config = ConfigDict(extra="forbid")

    camera_config: CameraConfig = Field(default_factory=CameraConfig)
    preflight: SfMPreflightConfig = Field(default_factory=SfMPreflightConfig)
    intrinsics: IntrinsicsConfig = Field(default_factory=IntrinsicsConfig)
    feature_extraction: FeatureExtractionConfig = Field(default_factory=FeatureExtractionConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    reconstruction: ReconstructionConfig = Field(default_factory=ReconstructionConfig)
    undistortion: UndistortionConfig = Field(default_factory=UndistortionConfig)
    dense: DenseConfig = Field(default_factory=DenseConfig)


class AdvancedConfig(BaseModel):
    """Advanced settings below the mandatory project/tools sections."""

    model_config = ConfigDict(extra="forbid")

    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    resume: ResumeConfig = Field(default_factory=ResumeConfig)
    sfm: SfMConfig = Field(default_factory=SfMConfig)
    splat: SplatConfig = Field(default_factory=SplatConfig)


class PipelineConfig(BaseModel):
    """Complete typed pipeline configuration for Feature 1."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    tools: ToolsConfig
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)

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
