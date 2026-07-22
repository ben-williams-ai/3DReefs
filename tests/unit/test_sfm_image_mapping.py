"""SfM image identity mapping checks."""

import json
from pathlib import Path

from reefs.preflight.images import ImageLayout
from reefs.sfm.pipeline import _write_image_mapping
from reefs.sfm.validation import create_sfm_paths
from reefs.runs.manifest import create_run_paths


def test_image_mapping_records_original_and_staged_names(tmp_path: Path) -> None:
    (tmp_path / "mapping").mkdir()
    run_paths = create_run_paths(tmp_path, run_id="mapping")
    paths = create_sfm_paths(run_paths)
    original = ImageLayout(kind="single", image_paths=[Path("a b.jpg")], camera_dirs=[])
    staged = ImageLayout(kind="single", image_paths=[Path("img_000001_deadbeef.jpg")], camera_dirs=[])

    output = _write_image_mapping(
        paths=paths,
        original=original,
        colmap=staged,
    )

    assert json.loads(output.read_text())["entries"] == [
        {"original": "a b.jpg", "staged": "img_000001_deadbeef.jpg"}
    ]
