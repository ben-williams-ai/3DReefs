"""Static safety-contract tests for the Nebius Stage 2 wrappers."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_worker_image_contains_metadata_recovery_tool_and_pinned_scientific_versions() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "libimage-exiftool-perl" in dockerfile
    assert "ARG COLMAP_REF=9c23f6942fe69962e06030905e77067c8673382f" in dockerfile
    assert "ARG LFS_COMMIT=6d591a34" in dockerfile


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
    assert 'sudo find "${eval_datasets_root}" -type l -delete' in worker


def test_stage2_source_upload_ignores_generated_patch_image_links() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert 'local source_patches="${OUT_ROOT}/project/runs/${RUN_ID}/splat/patches"' in worker
    assert '-path "*/selected_images/*" -type l -delete' in worker


def test_stage1_upload_preserves_inner_scientific_run_without_following_links() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert '"${WORKER_MODE}" == "stage1_sfm_eval"' in worker
    assert 'scientific_runs/${scientific_run_id}/' in worker
    assert "--no-follow-symlinks" in worker
    assert 'find "${eval_datasets_root}" -type l -delete' in worker
    assert "Scientific-run upload verification found differences" in worker


def test_stage2_source_recovery_uses_the_undistortion_only_entrypoint() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert '"${WORKER_MODE}" == "stage2_source_recovery"' in worker
    assert "source_job_args+=(--recover-undistortion-only)" in worker


def test_stage2_worker_restores_only_requested_and_full_resolution_source_trees() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_ablation_worker.sh").read_text(encoding="utf-8")

    assert 'TRAINING_WORKSPACE="undistorted_2048"' in worker
    assert '--exclude "*"' in worker
    assert '--include "sfm/${TRAINING_WORKSPACE}/*"' in worker
    assert '--include "sfm/undistorted_full_resolution/*"' in worker
    assert 'included_prefixes=[' in worker
    assert 'rmdir "${DATASET_DIR}/raw_images"' in worker
    assert 'sfm/${TRAINING_WORKSPACE}/images' in worker


def test_vm_cleanup_still_requires_successful_remote_exit_marker() -> None:
    launcher = (REPO_ROOT / "scripts" / "nebius" / "launch_worker_vm.sh").read_text(encoding="utf-8")

    assert 'if [[ "${code}" -ne 0 ]]' in launcher
    assert 'Preserving Nebius instance' in launcher
    assert "PIPELINE_EXIT:0\\nUPLOAD_STATUS:0" in launcher
    assert 'compute instance delete' in launcher
    assert 'BUCKET="${BUCKET:-3dreefs-ben-eu-north1}"' in launcher
    assert 'OUTPUT_PREFIX="${OUTPUT_PREFIX:-experiments/ablations}"' in launcher


def test_vm_launcher_isolated_known_hosts_for_recycled_public_ips() -> None:
    launcher = (REPO_ROOT / "scripts" / "nebius" / "launch_worker_vm.sh").read_text(encoding="utf-8")

    assert 'KNOWN_HOSTS_FILE="$(mktemp)"' in launcher
    assert 'UserKnownHostsFile="${KNOWN_HOSTS_FILE}"' in launcher
    assert 'scp "${SCP_OPTS[@]}"' in launcher
    assert 'rm -f "${USER_DATA}" "${ENV_FILE}" "${KNOWN_HOSTS_FILE}"' in launcher
