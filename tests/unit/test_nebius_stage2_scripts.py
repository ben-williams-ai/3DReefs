"""Static safety-contract tests for the Nebius Stage 2 wrappers."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_stage2_worker_cannot_route_probe_batches_through_sfm() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert 'elif [[ "${WORKER_MODE}" == "stage2_splat_eval" ]]' in worker
    assert 'run_stage2_batch' in worker
    assert '--phase splat' in worker
    assert '--job-id "${probe_id}"' in worker
    assert 'source manifest is not validated' in worker
    assert 'verify_checksums(' in worker


def test_stage2_worker_waits_for_verified_probe_upload_before_continuing() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert 'upload_completed_stage2_probes' in worker
    assert '--dryrun' in worker
    assert 'until [[ -f "${ack}" ]]' in worker
    assert 'UPLOAD_STATUS:0' in worker
    assert '--exclude "eval_datasets/*/*/images/*"' in worker


def test_stage2_worker_restores_only_requested_and_full_resolution_source_trees() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert 'TRAINING_WORKSPACE="undistorted_2048"' in worker
    assert '--exclude "*"' in worker
    assert '--include "sfm/${TRAINING_WORKSPACE}/*"' in worker
    assert '--include "sfm/undistorted_full_resolution/*"' in worker
    assert 'included_prefixes=[' in worker


def test_vm_cleanup_still_requires_successful_remote_exit_marker() -> None:
    launcher = (REPO_ROOT / "scripts" / "nebius" / "launch_worker_vm.sh").read_text(encoding="utf-8")

    assert 'if [[ "${code}" -ne 0 ]]' in launcher
    assert 'Preserving Nebius instance' in launcher
    assert "PIPELINE_EXIT:0\\nUPLOAD_STATUS:0" in launcher
    assert 'compute instance delete' in launcher
