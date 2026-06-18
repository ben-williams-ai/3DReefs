"""Tests for splat pipeline patch-generation wiring."""

from __future__ import annotations

from types import SimpleNamespace

from reefs.patches.bounds import PatchBounds
from reefs.splat import pipeline


def test_generate_patches_uses_internal_target_for_bounds_and_final_cap_for_validation(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}
    bounds = PatchBounds("p000", -1, 1, -1, 1, -1, 1, 0.1)

    def fake_generate_patch_bounds(images, *, max_cameras, buffer, points_xyz):
        calls["bounds_max_cameras"] = max_cameras
        return [bounds]

    def fake_select_patch_views(scene, item, *, max_cameras, all_bounds, external_support_fraction):
        calls["selection_max_cameras"] = max_cameras
        calls["selection_external_support_fraction"] = external_support_fraction
        return SimpleNamespace(bounds=item)

    def fake_export_patch_dataset(**kwargs):
        return {"patch_id": "p000"}

    def fake_validate_patch_metadata(patch_dir, *, max_cameras):
        calls["validation_max_cameras"] = max_cameras
        return {"patch_id": "p000"}

    monkeypatch.setattr(pipeline, "generate_patch_bounds", fake_generate_patch_bounds)
    monkeypatch.setattr(pipeline, "select_patch_views", fake_select_patch_views)
    monkeypatch.setattr(pipeline, "export_patch_dataset", fake_export_patch_dataset)
    monkeypatch.setattr(pipeline, "validate_patch_metadata", fake_validate_patch_metadata)
    monkeypatch.setattr(pipeline, "write_patch_summary", lambda *args, **kwargs: [])
    monkeypatch.setattr(pipeline, "write_patch_selection_diagnostics", lambda *args, **kwargs: [])
    monkeypatch.setattr(pipeline, "_patch_affecting_config", lambda config: {})

    config = SimpleNamespace(
        advanced=SimpleNamespace(
            splat=SimpleNamespace(
                patching=SimpleNamespace(
                    max_cameras=400,
                    external_support_fraction=0.10,
                    buffer=0.1,
                    patch_ids=None,
                )
            )
        )
    )
    preflight_result = SimpleNamespace(
        paths=SimpleNamespace(patches=tmp_path / "patches"),
        source=SimpleNamespace(paths=SimpleNamespace(images_dir=tmp_path / "run" / "sfm" / "undistorted" / "images")),
    )
    scene = SimpleNamespace(images=[], points=[])

    pipeline._generate_patches(config=config, preflight_result=preflight_result, source_sparse=tmp_path / "sparse", scene=scene)

    assert calls["bounds_max_cameras"] == 360
    assert calls["selection_max_cameras"] == 400
    assert calls["selection_external_support_fraction"] == 0.10
    assert calls["validation_max_cameras"] == 400
