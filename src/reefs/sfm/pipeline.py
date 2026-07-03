"""COLMAP SfM pipeline orchestration."""

from __future__ import annotations

import shutil
import sqlite3
import struct
from hashlib import blake2s
from dataclasses import dataclass, field
from pathlib import Path

from reefs.colmap.commands import (
    ColmapCommand,
    build_cross_camera_matcher_command,
    build_dense_commands,
    build_feature_extractor,
    build_matcher_commands,
    build_reconstruction_command,
    build_sparse_refinement_iteration_commands,
    build_undistorter_command,
    effective_undistortion_max_image_size,
)
from reefs.colmap.outputs import SparseModelSummary, list_sparse_models, select_sparse_model
from reefs.colmap.runner import CommandResult, run_colmap_command
from reefs.colour.pipeline import assert_colour_ready_for_handoff
from reefs.logging.timings import TimingRecorder
from reefs.preflight.images import ImageLayout
from reefs.preflight.images import detect_image_layout
from reefs.preflight.sfm import SfMPreflightResult
from reefs.config.models import ResumePolicy
from reefs.runs.recorder import RunRecorder
from reefs.sfm.cross_camera_pairs import (
    generate_cross_camera_pairs,
    write_pair_preview,
    write_pairs_file,
)
from reefs.sfm.validation import SfMPaths, create_sfm_paths, expand_sfm_steps
from reefs.sfm.intrinsics import (
    CameraIntrinsics,
    camera_intrinsics_by_group_from_sparse_text,
)


COLMAP_CAMERA_MODEL_IDS = {
    "SIMPLE_PINHOLE": 0,
    "PINHOLE": 1,
    "SIMPLE_RADIAL": 2,
    "RADIAL": 3,
    "OPENCV": 4,
    "OPENCV_FISHEYE": 5,
    "FULL_OPENCV": 6,
    "FOV": 7,
    "SIMPLE_RADIAL_FISHEYE": 8,
    "RADIAL_FISHEYE": 9,
    "THIN_PRISM_FISHEYE": 10,
}


@dataclass
class SfMRunResult:
    """Outputs and metadata from an SfM invocation."""

    paths: SfMPaths
    command_results: list[CommandResult] = field(default_factory=list)
    sparse_models: list[SparseModelSummary] = field(default_factory=list)
    selected_sparse_model: SparseModelSummary | None = None
    output_paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable result."""
        return {
            "database_path": str(self.paths.database),
            "sparse_root": str(self.paths.sparse),
            "selected_sparse_model": self.selected_sparse_model.as_dict()
            if self.selected_sparse_model
            else None,
            "sparse_models": [summary.as_dict() for summary in self.sparse_models],
            "output_paths": self.output_paths,
            "warnings": self.warnings,
            "commands": [result.as_dict() for result in self.command_results],
        }


@dataclass(frozen=True)
class IntrinsicsPrecalculationResult:
    """Outputs from the optional intrinsics subset reconstruction."""

    camera_params: str | None
    camera_intrinsics_by_group: dict[str, CameraIntrinsics] | None
    command_results: list[CommandResult]
    sparse_text_path: Path | None = None


def effective_max_num_features(*, configured: int, total_images: int) -> int:
    """Apply the configured large-collection protective feature count."""
    if total_images > 10000 and configured == 8192:
        return 4096
    return configured


def _step_requested(*, requested: set[str], run_all: bool, canonical: str, aliases: set[str] | None = None) -> bool:
    """Return whether a canonical stage or one of its aliases was requested."""
    return run_all or canonical in requested or bool((aliases or set()).intersection(requested))


def _run(
    command: ColmapCommand,
    *,
    paths: SfMPaths,
    timings: TimingRecorder,
    recorder: RunRecorder | None = None,
) -> CommandResult:
    if recorder:
        recorder.stage_started(command.stage, command_args=command.args)
    with timings.stage(command.stage):
        result = run_colmap_command(command, log_path=paths.colmap_log)
    if recorder:
        recorder.stage_completed(command.stage)
    return result


def _copy_selected_sparse(selected: SparseModelSummary, destination: Path) -> Path:
    return _copy_sparse_path(selected.path, destination)


def _copy_sparse_path(source: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def _require_existing_file(path: Path, *, stage: str, description: str) -> None:
    """Fail before a resumed stage when a required prior output is absent."""
    if not path.exists():
        raise ValueError(f"Cannot run {stage} because required {description} is missing: {path}")


def _clear_reconstruction_outputs(paths: SfMPaths) -> None:
    """Remove generated reconstruction outputs before an explicit rerun."""
    for path in [paths.sparse, paths.selected_sparse, paths.selected_sparse_text, paths.refined_sparse]:
        if path.exists():
            shutil.rmtree(path)
    paths.sparse.mkdir(parents=True, exist_ok=True)


def _clear_cross_camera_outputs(paths: SfMPaths) -> None:
    """Remove generated cross-camera pair outputs before match overwrite."""
    if paths.cross_camera_pairs.exists():
        shutil.rmtree(paths.cross_camera_pairs)


def _clear_colmap_matching_tables(database: Path) -> None:
    """Remove matcher outputs from a COLMAP database before full match overwrite."""
    if not database.exists():
        return
    try:
        with sqlite3.connect(database) as connection:
            for table in ["matches", "two_view_geometries"]:
                try:
                    connection.execute(f"DELETE FROM {table}")
                except sqlite3.Error:
                    pass
            connection.commit()
    except sqlite3.Error:
        return


def _remove_colmap_database(database: Path) -> None:
    """Remove a COLMAP database before rebuilding feature extraction outputs."""
    if database.exists():
        database.unlink()


def _has_whitespace_image_names(layout: ImageLayout) -> bool:
    """Return whether any COLMAP image name would break matches_importer pairs."""
    return any(any(character.isspace() for character in path.as_posix()) for path in layout.relative_image_paths)


def _clean_path_part(value: str) -> str:
    """Return a conservative filesystem-safe path component."""
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "image"


def _stable_suffix(value: str) -> str:
    """Return a short stable suffix for collision-proof staged names."""
    return blake2s(value.encode("utf-8", errors="surrogatepass"), digest_size=4).hexdigest()


def _safe_path_part(value: str) -> str:
    """Return the staged path component for an original path component."""
    return f"{_clean_path_part(value)}_{_stable_suffix(value)}"


def _staged_camera_group_aliases(layout: ImageLayout) -> dict[str, str]:
    """Map staged top-level camera folders back to original camera folders."""
    aliases: dict[str, str] = {}
    for relative_path in layout.relative_image_paths:
        if len(relative_path.parts) <= 1:
            continue
        original_group = relative_path.parts[0]
        aliases[_safe_path_part(original_group)] = original_group
    return aliases


def _stage_colmap_safe_images(*, source_root: Path, layout: ImageLayout, target_root: Path) -> ImageLayout:
    """Copy images to COLMAP-safe names while preserving the pipeline order."""
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    counters: dict[Path, int] = {}
    staged_paths: list[Path] = []
    for relative_path in layout.relative_image_paths:
        parent = relative_path.parent if relative_path.parent != Path(".") else Path()
        safe_parent = Path(*[_safe_path_part(part) for part in parent.parts]) if parent.parts else Path()
        counters[safe_parent] = counters.get(safe_parent, 0) + 1
        suffix = relative_path.suffix.lower() or ".jpg"
        staged_relative = safe_parent / f"img_{counters[safe_parent]:06d}_{_stable_suffix(relative_path.as_posix())}{suffix}"
        target = target_root / staged_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative_path, target)
        staged_paths.append(staged_relative)

    camera_dirs = sorted({path.parts[0] for path in staged_paths if len(path.parts) > 1}, key=str)
    return ImageLayout(
        kind=layout.kind,
        image_paths=staged_paths,
        camera_dirs=camera_dirs,
        ordering_reports=layout.ordering_reports,
    )


def _sfm_image_inputs(*, config, source_root: Path, layout: ImageLayout, paths: SfMPaths) -> tuple[Path, ImageLayout, list[str]]:
    """Return the image root/layout COLMAP should use for this run."""
    staged_root = paths.root / "staged_raw_images"
    if staged_root.exists():
        return staged_root, detect_image_layout(staged_root), []

    cross_config = config.advanced.sfm.matching.cross_camera_pairs
    if cross_config.enabled and cross_config.run_matching_pass and _has_whitespace_image_names(layout):
        staged_layout = _stage_colmap_safe_images(
            source_root=source_root,
            layout=layout,
            target_root=staged_root,
        )
        return staged_root, staged_layout, [
            "Staged COLMAP-safe raw image copies because cross-camera pair matching cannot parse whitespace in image names."
        ]
    return source_root, layout, []


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    """Return whether a SQLite table exists."""
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_count(connection: sqlite3.Connection, table: str) -> int:
    """Return a table row count, or zero when the table is absent."""
    if not _table_exists(connection, table):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _update_id_column(
    connection: sqlite3.Connection,
    *,
    table: str,
    column: str,
    mapping: dict[int, int],
) -> None:
    """Update integer IDs in one table column."""
    if not _table_exists(connection, table):
        return
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        return
    for old_id, new_id in mapping.items():
        connection.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (new_id, old_id))


def _reindex_colmap_database_images(*, database: Path, ordered_image_names: list[str]) -> dict[str, int]:
    """Rewrite pre-match COLMAP image IDs to match pipeline image order."""
    if not database.exists():
        raise ValueError(f"Cannot reindex COLMAP image order because database is missing: {database}")
    if len(set(ordered_image_names)) != len(ordered_image_names):
        raise ValueError("Cannot reindex COLMAP image order because ordered image names contain duplicates")

    with sqlite3.connect(database) as connection:
        if _table_count(connection, "matches") or _table_count(connection, "two_view_geometries"):
            raise ValueError("Cannot reindex COLMAP image order after matching tables have been populated")

        rows = connection.execute("SELECT image_id, name FROM images ORDER BY image_id").fetchall()
        if not rows:
            raise ValueError("Cannot reindex COLMAP image order because the database contains no images")
        old_id_by_name = {str(name): int(image_id) for image_id, name in rows}
        if set(old_id_by_name) != set(ordered_image_names):
            missing = sorted(set(ordered_image_names) - set(old_id_by_name))
            extra = sorted(set(old_id_by_name) - set(ordered_image_names))
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing[:10]))
            if extra:
                details.append("extra: " + ", ".join(extra[:10]))
            raise ValueError("COLMAP database images do not match ordered image list: " + "; ".join(details))

        final_mapping = {old_id_by_name[name]: index for index, name in enumerate(ordered_image_names, start=1)}
        if all(old_id == new_id for old_id, new_id in final_mapping.items()):
            return {name: old_id_by_name[name] for name in ordered_image_names}

        temp_base = 1_000_000_000
        if temp_base + max(final_mapping) >= 2_147_483_647:
            raise ValueError("Cannot reindex COLMAP image order because image IDs exceed the safe temporary range")
        temp_mapping = {old_id: temp_base + old_id for old_id in final_mapping}

        connection.execute("PRAGMA foreign_keys = OFF")
        for table, column in [
            ("images", "image_id"),
            ("keypoints", "image_id"),
            ("descriptors", "image_id"),
            ("frame_data", "data_id"),
            ("pose_priors", "corr_data_id"),
        ]:
            _update_id_column(connection, table=table, column=column, mapping=temp_mapping)
        for table, column in [
            ("images", "image_id"),
            ("keypoints", "image_id"),
            ("descriptors", "image_id"),
            ("frame_data", "data_id"),
            ("pose_priors", "corr_data_id"),
        ]:
            _update_id_column(
                connection,
                table=table,
                column=column,
                mapping={temp_mapping[old_id]: new_id for old_id, new_id in final_mapping.items()},
            )
        if _table_exists(connection, "sqlite_sequence"):
            connection.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'images'", (len(ordered_image_names),))
        connection.commit()
        return {name: index for index, name in enumerate(ordered_image_names, start=1)}


def _camera_group_from_database_image_name(name: str) -> str:
    """Return the camera group for a COLMAP database image name."""
    parts = Path(name).parts
    if "raw_images" in parts:
        index = parts.index("raw_images")
        if index + 2 < len(parts):
            return parts[index + 1]
    return parts[0] if len(parts) > 1 else "single"


def _camera_model_id(model: str) -> int:
    """Return COLMAP's numeric camera model ID for a model name."""
    try:
        return COLMAP_CAMERA_MODEL_IDS[model]
    except KeyError as exc:
        raise ValueError(f"Unsupported COLMAP camera model for DB update: {model}") from exc


def _camera_params_blob(params: tuple[float, ...]) -> bytes:
    """Pack COLMAP camera params as a contiguous float64 blob."""
    return struct.pack(f"<{len(params)}d", *params)


def _seed_database_camera_intrinsics(
    *,
    database: Path,
    intrinsics_by_group: dict[str, CameraIntrinsics],
    camera_group_aliases: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Update full COLMAP DB camera rows with per-folder precalculated intrinsics."""
    if not database.exists():
        raise ValueError(f"Cannot seed intrinsics because COLMAP database is missing: {database}")
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(cameras)").fetchall()}
        required = {"camera_id", "model", "width", "height", "params"}
        if not required.issubset(columns):
            raise ValueError(f"COLMAP database cameras table is missing columns: {sorted(required - columns)}")

        rows = connection.execute("SELECT name, camera_id FROM images").fetchall()
        if not rows:
            raise ValueError("COLMAP database contains no image camera assignments")
        camera_ids_by_group: dict[str, set[int]] = {}
        for image_name, camera_id in rows:
            group = _camera_group_from_database_image_name(str(image_name))
            group = (camera_group_aliases or {}).get(group, group)
            camera_ids_by_group.setdefault(group, set()).add(int(camera_id))

        expected_groups = set(intrinsics_by_group)
        actual_groups = set(camera_ids_by_group)
        if expected_groups != actual_groups:
            raise ValueError(
                "Precalculated intrinsics camera groups do not match the full COLMAP database: "
                f"expected {sorted(expected_groups)}, got {sorted(actual_groups)}"
            )

        seeded: dict[str, dict[str, object]] = {}
        for group, camera_ids in sorted(camera_ids_by_group.items()):
            if len(camera_ids) != 1:
                raise ValueError(
                    f"Camera group {group!r} maps to multiple full-run COLMAP camera IDs: "
                    f"{sorted(camera_ids)}"
                )
            full_camera_id = next(iter(camera_ids))
            intrinsics = intrinsics_by_group[group]
            model_id = _camera_model_id(intrinsics.model)
            assignments: list[object] = [
                model_id,
                intrinsics.width,
                intrinsics.height,
                sqlite3.Binary(_camera_params_blob(intrinsics.params)),
            ]
            set_clause = "model = ?, width = ?, height = ?, params = ?"
            if "prior_focal_length" in columns:
                set_clause += ", prior_focal_length = ?"
                assignments.append(1)
            assignments.append(full_camera_id)
            connection.execute(
                f"UPDATE cameras SET {set_clause} WHERE camera_id = ?",
                assignments,
            )
            seeded[group] = {
                "full_camera_id": full_camera_id,
                "source_camera_id": intrinsics.camera_id,
                "model": intrinsics.model,
                "width": intrinsics.width,
                "height": intrinsics.height,
                "params": list(intrinsics.params),
            }
        connection.commit()
    return seeded


def _prepare_intrinsics_subset(*, source_root: Path, selected_images: dict[str, list[str]], target_root: Path) -> None:
    """Create an image subset for intrinsics pre-calculation."""
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True)
    for images in selected_images.values():
        for relative_name in images:
            relative_path = Path(relative_name)
            target_path = target_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_root / relative_path, target_path)


def _run_intrinsics_subset(
    *,
    config,
    layout: ImageLayout,
    paths: SfMPaths,
    subset_root: Path,
    subset_database: Path,
    subset_sparse: Path,
    subset_selected: Path,
    subset_text: Path,
    ordered_image_names: list[str],
    max_num_features: int,
    timings: TimingRecorder,
    recorder: RunRecorder | None = None,
) -> tuple[dict[str, CameraIntrinsics], list[CommandResult]]:
    """Run one intrinsics subset reconstruction and return camera-group intrinsics."""
    subset_sparse.mkdir(parents=True, exist_ok=True)
    _remove_colmap_database(subset_database)
    results: list[CommandResult] = []
    feature_command = build_feature_extractor(
        config=config,
        layout=layout,
        database_path=subset_database,
        image_path=subset_root,
        max_num_features=max_num_features,
        camera_params=None,
    )
    results.append(
        _run(
            ColmapCommand(stage="sfm.intrinsics.extract", args=feature_command.args),
            paths=paths,
            timings=timings,
            recorder=recorder,
        )
    )
    _reindex_colmap_database_images(
        database=subset_database,
        ordered_image_names=ordered_image_names,
    )
    for command in build_matcher_commands(
        config=config,
        database_path=subset_database,
        vocab_tree_path=config.tools.vocab_tree_path,
    ):
        results.append(
            _run(
                ColmapCommand(stage=command.stage.replace("sfm.match", "sfm.intrinsics.match"), args=command.args),
                paths=paths,
                timings=timings,
                recorder=recorder,
            )
        )
    reconstruction_command = build_reconstruction_command(
        config=config,
        database_path=subset_database,
        image_path=subset_root,
        output_path=subset_sparse,
    )
    results.append(_run(_with_refined_intrinsics(reconstruction_command), paths=paths, timings=timings, recorder=recorder))
    selected = select_sparse_model(list_sparse_models(subset_sparse))
    selected_sparse_path = _copy_selected_sparse(selected, subset_selected)
    _export_sparse_text(
        colmap_bin=config.tools.colmap_bin,
        input_path=selected_sparse_path,
        output_path=subset_text,
        paths=paths,
        timings=timings,
        recorder=recorder,
    )
    return (
        camera_intrinsics_by_group_from_sparse_text(
            cameras_txt=subset_text / "cameras.txt",
            images_txt=subset_text / "images.txt",
        ),
        results,
    )


def _export_sparse_text(
    *,
    colmap_bin: str,
    input_path: Path,
    output_path: Path,
    paths: SfMPaths,
    timings: TimingRecorder,
    recorder: RunRecorder | None = None,
) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    command = ColmapCommand(
        stage="sfm.reconstruct.export_text",
        args=[
            colmap_bin,
            "model_converter",
            "--input_path",
            str(input_path),
            "--output_path",
            str(output_path),
            "--output_type",
            "TXT",
        ],
    )
    _run(command, paths=paths, timings=timings, recorder=recorder)


def _with_refined_intrinsics(command: ColmapCommand) -> ColmapCommand:
    """Return a reconstruction command with intrinsics refinement enabled."""
    args = list(command.args)
    for flag in [
        "--GlobalMapper.ba_refine_focal_length",
        "--GlobalMapper.ba_refine_principal_point",
        "--GlobalMapper.ba_refine_extra_params",
        "--Mapper.ba_refine_focal_length",
        "--Mapper.ba_refine_principal_point",
        "--Mapper.ba_refine_extra_params",
    ]:
        if flag in args:
            args[args.index(flag) + 1] = "1"
    return ColmapCommand(stage="sfm.intrinsics.reconstruct", args=args)


def _run_intrinsics_precalculation(
    *,
    config,
    derived_paths,
    layout: ImageLayout,
    paths: SfMPaths,
    preflight_result: SfMPreflightResult,
    max_num_features: int,
    timings: TimingRecorder,
    recorder: RunRecorder | None = None,
) -> IntrinsicsPrecalculationResult:
    """Run a subset reconstruction to estimate camera parameters."""
    selection = preflight_result.intrinsics_selection
    if selection.source == "user_cameras_file":
        return IntrinsicsPrecalculationResult(
            camera_params=selection.camera_params,
            camera_intrinsics_by_group=selection.camera_intrinsics_by_group,
            command_results=[],
        )
    if selection.source != "precalculated":
        return IntrinsicsPrecalculationResult(
            camera_params=None,
            camera_intrinsics_by_group=None,
            command_results=[],
        )

    results: list[CommandResult] = []
    intrinsics_by_group: dict[str, CameraIntrinsics] = {}
    subset_text = paths.root / "intrinsics_subset" / "selected_sparse_txt"
    if layout.kind == "multi":
        for group, images in sorted(selection.selected_images.items()):
            group_root = paths.root / "intrinsics_subset" / group
            _prepare_intrinsics_subset(
                source_root=derived_paths.raw_images,
                selected_images={group: images},
                target_root=group_root / "images",
            )
            group_intrinsics, group_results = _run_intrinsics_subset(
                config=config,
                layout=layout,
                paths=paths,
                subset_root=group_root / "images",
                subset_database=group_root / "database.db",
                subset_sparse=group_root / "sparse",
                subset_selected=group_root / "selected_sparse",
                subset_text=group_root / "selected_sparse_txt",
                ordered_image_names=images,
                max_num_features=max_num_features,
                timings=timings,
                recorder=recorder,
            )
            if set(group_intrinsics) != {group}:
                raise ValueError(
                    f"Intrinsics pre-calculation for {group!r} returned camera groups "
                    f"{sorted(group_intrinsics)}"
                )
            intrinsics_by_group.update(group_intrinsics)
            results.extend(group_results)
        subset_text = paths.root / "intrinsics_subset"
    else:
        subset_root = paths.root / "intrinsics_subset" / "images"
        _prepare_intrinsics_subset(
            source_root=derived_paths.raw_images,
            selected_images=selection.selected_images,
            target_root=subset_root,
        )
        intrinsics_by_group, results = _run_intrinsics_subset(
            config=config,
            layout=layout,
            paths=paths,
            subset_root=subset_root,
            subset_database=paths.root / "intrinsics_subset" / "database.db",
            subset_sparse=paths.root / "intrinsics_subset" / "sparse",
            subset_selected=paths.root / "intrinsics_subset" / "selected_sparse",
            subset_text=subset_text,
            ordered_image_names=[name for images in selection.selected_images.values() for name in images],
            max_num_features=max_num_features,
            timings=timings,
            recorder=recorder,
        )
    camera_params = None
    if layout.kind == "single":
        camera_params = next(iter(intrinsics_by_group.values())).camera_params_string()
    return IntrinsicsPrecalculationResult(
        camera_params=camera_params,
        camera_intrinsics_by_group=intrinsics_by_group if layout.kind == "multi" else None,
        command_results=results,
        sparse_text_path=subset_text,
    )


def _select_undistortion_image_root(*, config, derived_paths, run_paths=None) -> tuple[Path, str]:
    setting = config.advanced.sfm.undistortion.image_source
    if setting in {"auto", "raw"}:
        return derived_paths.raw_images, "raw"
    return derived_paths.raw_images, "raw"


def _prepare_dense_output_directories(workspace_path: Path) -> None:
    """Create nested stereo output directories for multi-camera image names."""
    images_dir = workspace_path / "images"
    stereo_dir = workspace_path / "stereo"
    output_roots = [
        stereo_dir / "depth_maps",
        stereo_dir / "normal_maps",
        stereo_dir / "consistency_graphs",
    ]
    for root in output_roots:
        root.mkdir(parents=True, exist_ok=True)
    if not images_dir.exists():
        return
    for image_path in images_dir.rglob("*"):
        if not image_path.is_file():
            continue
        relative_parent = image_path.relative_to(images_dir).parent
        if relative_parent == Path("."):
            continue
        for root in output_roots:
            (root / relative_parent).mkdir(parents=True, exist_ok=True)


def _prepare_cross_camera_pairs(*, config, layout: ImageLayout, paths: SfMPaths) -> tuple[Path | None, list[str]]:
    """Write optional cross-camera pair artefacts for review or matching."""
    cross_config = config.advanced.sfm.matching.cross_camera_pairs
    if not cross_config.enabled:
        return None, []
    generated = generate_cross_camera_pairs(
        layout,
        index_window=cross_config.index_window,
        ordering=cross_config.ordering,
    )
    pairs_path = paths.cross_camera_pairs / "pairs.txt"
    write_pairs_file(generated.pairs, pairs_path)
    write_pair_preview(
        generated,
        preview_path=paths.cross_camera_pairs / "pairs_preview.txt",
        summary_path=paths.cross_camera_pairs / "summary.json",
        preview_count=cross_config.scratch_preview_count,
    )
    warnings = [str(warning) for warning in generated.summary.get("warnings", [])]
    return pairs_path if generated.pairs else None, warnings


def _run_sparse_refinement(
    *,
    config,
    database_path: Path,
    image_path: Path,
    input_path: Path,
    paths: SfMPaths,
    timings: TimingRecorder,
    recorder: RunRecorder | None,
    result: SfMRunResult,
) -> Path:
    """Run optional sparse refinement and return the model path for undistortion."""
    refinement = config.advanced.sfm.sparse_refinement
    if not refinement.enabled:
        return input_path
    if paths.refined_sparse.exists():
        shutil.rmtree(paths.refined_sparse)
    paths.refined_sparse.mkdir(parents=True, exist_ok=True)
    original = select_sparse_model(list_sparse_models(input_path))
    current = input_path
    try:
        for iteration in range(1, refinement.repeats + 1):
            iteration_path = paths.refined_sparse / f"iter_{iteration:02d}"
            commands, current = build_sparse_refinement_iteration_commands(
                config=config,
                database_path=database_path,
                image_path=image_path,
                input_path=current,
                iteration_path=iteration_path,
                iteration=iteration,
            )
            for command in commands:
                if "--output_path" in command.args:
                    Path(command.args[command.args.index("--output_path") + 1]).mkdir(parents=True, exist_ok=True)
                result.command_results.append(_run(command, paths=paths, timings=timings, recorder=recorder))
            summary = select_sparse_model(list_sparse_models(current))
            if summary.registered_images <= 0 or summary.points3d <= 0:
                raise ValueError(f"Sparse refinement produced an invalid model at {current}")
            if summary.registered_images < original.registered_images:
                result.warnings.append(
                    "Sparse refinement reduced registered images from "
                    f"{original.registered_images} to {summary.registered_images}."
                )
            if original.points3d and summary.points3d < original.points3d * 0.5:
                result.warnings.append(
                    "Sparse refinement removed more than half of sparse points "
                    f"({original.points3d} -> {summary.points3d})."
                )
        final_path = _copy_sparse_path(current, paths.refined_sparse / "final")
        result.output_paths["refined_sparse"] = str(final_path)
        return final_path
    except Exception:
        if refinement.allow_fallback:
            result.warnings.append("Sparse refinement failed; falling back to selected sparse model.")
            return input_path
        raise


def run_sfm_pipeline(
    *,
    config,
    derived_paths,
    layout: ImageLayout,
    run_paths,
    preflight_result: SfMPreflightResult,
    requested_steps: list[str],
    timings: TimingRecorder,
    recorder: RunRecorder | None = None,
    resume_policy: ResumePolicy = ResumePolicy.PROMPT,
) -> SfMRunResult:
    """Run requested COLMAP SfM stages."""
    sfm_paths = create_sfm_paths(run_paths)
    requested = set(expand_sfm_steps(requested_steps))
    run_all = "sfm" in requested_steps
    result = SfMRunResult(paths=sfm_paths, warnings=list(preflight_result.warnings))
    total_images = len(layout.relative_image_paths)
    max_num_features = effective_max_num_features(
        configured=config.advanced.sfm.feature_extraction.max_num_features,
        total_images=total_images,
    )
    result.output_paths["effective_sfm_settings"] = {
        "feature_type": config.advanced.sfm.feature_extraction.type,
        "feature_extraction_max_image_size": config.advanced.sfm.feature_extraction.max_image_size,
        "effective_max_num_features": max_num_features,
        "undistortion_max_image_size": config.advanced.sfm.undistortion.max_image_size,
        "undistortion_follow_feature_extraction_max_image_size": (
            config.advanced.sfm.undistortion.follow_feature_extraction_max_image_size
        ),
        "undistortion_fallback_max_image_size": config.advanced.sfm.undistortion.fallback_max_image_size,
        "effective_undistortion_max_image_size": effective_undistortion_max_image_size(config),
    }
    sfm_image_root = derived_paths.raw_images
    sfm_layout = layout

    camera_params = preflight_result.intrinsics_selection.camera_params
    camera_intrinsics_by_group = preflight_result.intrinsics_selection.camera_intrinsics_by_group
    if _step_requested(
        requested=requested,
        run_all=run_all,
        canonical="sfm.intrinsics",
        aliases={"sfm.extract", "sfm.feature_extraction"},
    ):
        intrinsics_precalculation = _run_intrinsics_precalculation(
            config=config,
            derived_paths=derived_paths,
            layout=layout,
            paths=sfm_paths,
            preflight_result=preflight_result,
            max_num_features=max_num_features,
            timings=timings,
            recorder=recorder,
        )
        result.command_results.extend(intrinsics_precalculation.command_results)
        camera_params = intrinsics_precalculation.camera_params or camera_params
        camera_intrinsics_by_group = (
            intrinsics_precalculation.camera_intrinsics_by_group or camera_intrinsics_by_group
        )
        if camera_params:
            result.output_paths["intrinsics_camera_params"] = camera_params
        if camera_intrinsics_by_group:
            result.output_paths["intrinsics_camera_groups"] = {
                group: intrinsics.as_dict() for group, intrinsics in camera_intrinsics_by_group.items()
            }
        if intrinsics_precalculation.sparse_text_path:
            result.output_paths["intrinsics_sparse_text"] = str(intrinsics_precalculation.sparse_text_path)

    sfm_image_root, sfm_layout, staging_warnings = _sfm_image_inputs(
        config=config,
        source_root=derived_paths.raw_images,
        layout=layout,
        paths=sfm_paths,
    )
    result.warnings.extend(staging_warnings)
    if sfm_image_root != derived_paths.raw_images:
        result.output_paths["staged_raw_images"] = str(sfm_image_root)

    if _step_requested(
        requested=requested,
        run_all=run_all,
        canonical="sfm.extract",
        aliases={"sfm.feature_extraction"},
    ):
        if resume_policy == ResumePolicy.OVERWRITE:
            _remove_colmap_database(sfm_paths.database)
        command = build_feature_extractor(
            config=config,
            layout=sfm_layout,
            database_path=sfm_paths.database,
            image_path=sfm_image_root,
            max_num_features=max_num_features,
            camera_params=camera_params if sfm_layout.kind == "single" else None,
        )
        result.command_results.append(_run(command, paths=sfm_paths, timings=timings, recorder=recorder))
        _reindex_colmap_database_images(
            database=sfm_paths.database,
            ordered_image_names=[path.as_posix() for path in sfm_layout.relative_image_paths],
        )
        if sfm_layout.kind == "multi" and camera_intrinsics_by_group:
            result.output_paths["intrinsics_database_seed"] = _seed_database_camera_intrinsics(
                database=sfm_paths.database,
                intrinsics_by_group=camera_intrinsics_by_group,
                camera_group_aliases=_staged_camera_group_aliases(layout)
                if sfm_image_root != derived_paths.raw_images
                else None,
            )

    matcher_commands = build_matcher_commands(
        config=config,
        database_path=sfm_paths.database,
        vocab_tree_path=config.tools.vocab_tree_path,
    )
    if run_all or "sfm.match" in requested or any(command.stage in requested for command in matcher_commands):
        _require_existing_file(sfm_paths.database, stage="sfm.match", description="COLMAP database")
        if "sfm.match" in requested and resume_policy == ResumePolicy.OVERWRITE:
            _clear_colmap_matching_tables(sfm_paths.database)
            _clear_cross_camera_outputs(sfm_paths)
        for command in matcher_commands:
            if not (run_all or "sfm.match" in requested or command.stage in requested):
                continue
            result.command_results.append(_run(command, paths=sfm_paths, timings=timings, recorder=recorder))
        cross_config = config.advanced.sfm.matching.cross_camera_pairs
        if cross_config.enabled:
            pairs_path, pair_warnings = _prepare_cross_camera_pairs(config=config, layout=sfm_layout, paths=sfm_paths)
            result.warnings.extend(pair_warnings)
            result.output_paths["cross_camera_pairs"] = str(sfm_paths.cross_camera_pairs)
            if cross_config.run_matching_pass and pairs_path is not None:
                command = build_cross_camera_matcher_command(
                    config=config,
                    database_path=sfm_paths.database,
                    pairs_path=pairs_path,
                )
                result.command_results.append(_run(command, paths=sfm_paths, timings=timings, recorder=recorder))

    if _step_requested(requested=requested, run_all=run_all, canonical="sfm.reconstruct"):
        _require_existing_file(sfm_paths.database, stage="sfm.reconstruct", description="COLMAP database")
        if resume_policy == ResumePolicy.OVERWRITE:
            _clear_reconstruction_outputs(sfm_paths)
        command = build_reconstruction_command(
            config=config,
            database_path=sfm_paths.database,
            image_path=sfm_image_root,
            output_path=sfm_paths.sparse,
        )
        result.command_results.append(_run(command, paths=sfm_paths, timings=timings, recorder=recorder))
        sparse_models = list_sparse_models(sfm_paths.sparse)
        selected = select_sparse_model(sparse_models)
        selected_sparse_path = _copy_selected_sparse(selected, sfm_paths.selected_sparse)
        _export_sparse_text(
            colmap_bin=config.tools.colmap_bin,
            input_path=selected_sparse_path,
            output_path=sfm_paths.selected_sparse_text,
            paths=sfm_paths,
            timings=timings,
            recorder=recorder,
        )
        text_summary = select_sparse_model(list_sparse_models(sfm_paths.selected_sparse_text))
        result.sparse_models = [
            SparseModelSummary(
                model_id=summary.model_id,
                path=summary.path,
                registered_images=summary.registered_images,
                points3d=summary.points3d,
                selected=summary.model_id == selected.model_id,
            )
            for summary in sparse_models
        ]
        result.selected_sparse_model = SparseModelSummary(
            model_id=selected.model_id,
            path=selected_sparse_path,
            registered_images=text_summary.registered_images,
            points3d=text_summary.points3d,
            selected=True,
        )
        if len(sparse_models) > 1:
            result.warnings.append(
                "Reconstruction produced multiple sparse models; selected the model with the most registered images."
            )
        _run_sparse_refinement(
            config=config,
            database_path=sfm_paths.database,
            image_path=sfm_image_root,
            input_path=selected_sparse_path,
            paths=sfm_paths,
            timings=timings,
            recorder=recorder,
            result=result,
        )

    if (
        config.advanced.sfm.sparse_refinement.enabled
        and _step_requested(requested=requested, run_all=False, canonical="sfm.refine")
        and not _step_requested(requested=requested, run_all=run_all, canonical="sfm.reconstruct")
    ):
        _require_existing_file(sfm_paths.database, stage="sfm.refine", description="COLMAP database")
        if not sfm_paths.selected_sparse.exists():
            raise ValueError("Cannot refine because selected sparse model is missing")
        if resume_policy == ResumePolicy.OVERWRITE and sfm_paths.refined_sparse.exists():
            shutil.rmtree(sfm_paths.refined_sparse)
        _run_sparse_refinement(
            config=config,
            database_path=sfm_paths.database,
            image_path=sfm_image_root,
            input_path=sfm_paths.selected_sparse,
            paths=sfm_paths,
            timings=timings,
            recorder=recorder,
            result=result,
        )

    if run_all or "sfm.undistort" in requested:
        if not sfm_paths.selected_sparse.exists():
            raise ValueError("Cannot undistort because selected sparse model is missing")
        if sfm_paths.undistorted.exists() and resume_policy == ResumePolicy.OVERWRITE:
            shutil.rmtree(sfm_paths.undistorted)
            if recorder:
                recorder.update_manifest(
                    generated_output_events=[
                        *recorder.manifest.get("generated_output_events", []),
                        {
                            "stage": "sfm.undistort",
                            "action": "deleted_existing_output",
                            "path": str(sfm_paths.undistorted),
                        },
                    ]
                )
        if sfm_image_root != derived_paths.raw_images:
            image_root, image_source = sfm_image_root, "staged_raw"
        else:
            image_root, image_source = _select_undistortion_image_root(
                config=config,
                derived_paths=derived_paths,
                run_paths=run_paths,
            )
        command = build_undistorter_command(
            config=config,
            image_path=image_root,
            input_path=(
                sfm_paths.refined_sparse / "final"
                if config.advanced.sfm.sparse_refinement.enabled
                and (sfm_paths.refined_sparse / "final").exists()
                else sfm_paths.selected_sparse
            ),
            output_path=sfm_paths.undistorted,
        )
        result.command_results.append(_run(command, paths=sfm_paths, timings=timings, recorder=recorder))
        result.output_paths["sparse_image_source"] = "raw"
        result.output_paths["undistortion_image_source"] = image_source
        result.output_paths["undistorted_images"] = str(sfm_paths.undistorted / "images")
        result.output_paths["undistorted_sparse"] = str(sfm_paths.undistorted / "sparse")
        result.output_paths["undistorted_intrinsics"] = str(sfm_paths.undistorted / "sparse" / "cameras.bin")

    if config.advanced.sfm.dense.enabled and (run_all or "sfm.dense" in requested or "sfm.mesh" in requested):
        _prepare_dense_output_directories(sfm_paths.undistorted)
        for command in build_dense_commands(config=config, workspace_path=sfm_paths.undistorted):
            result.command_results.append(_run(command, paths=sfm_paths, timings=timings, recorder=recorder))
        result.output_paths["dense_workspace"] = str(sfm_paths.undistorted)
        if config.advanced.sfm.dense.mesh.enabled:
            mesh_name = f"meshed-{config.advanced.sfm.dense.mesh.method}.ply"
            result.output_paths["mesh"] = str(sfm_paths.undistorted / mesh_name)

    return result
