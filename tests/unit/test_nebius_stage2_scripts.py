"""Static safety-contract tests for the Nebius Stage 2 wrappers."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_worker_image_contains_metadata_recovery_tool_and_pinned_scientific_versions() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "libimage-exiftool-perl" in dockerfile
    assert "ARG COLMAP_REF=9c23f6942fe69962e06030905e77067c8673382f" in dockerfile
    assert "ARG LFS_COMMIT=6d591a34" in dockerfile
    assert 'LABEL org.opencontainers.image.revision="${GIT_COMMIT}"' in dockerfile
    assert "COPY src ./src" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile


def test_stage2_worker_cannot_route_probe_batches_through_sfm() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")

    assert 'elif [[ "${WORKER_MODE}" == "stage2_splat_eval" ]]' in worker
    assert 'run_stage2_batch' in worker
    assert '--phase splat' in worker
    assert '--job-id "${probe_id}"' in worker
    assert 'source manifest is not validated' in worker
    assert 'verify_checksums(' in worker


def test_stage2_worker_waits_for_verified_probe_upload_before_continuing() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")

    assert 'upload_completed_stage2_probes' in worker
    assert '--dryrun' in worker
    assert 'until [[ -f "${ack}" ]]' in worker
    assert 'UPLOAD_STATUS:0' in worker
    assert '--exclude "eval_datasets/*/*/images/*"' in worker
    assert 'sudo find "${eval_datasets_root}" -type l -delete' in worker
    assert worker.count("--no-follow-symlinks") >= 6


def test_stage2_source_upload_ignores_generated_patch_image_links() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")

    assert 'local source_patches="${OUT_ROOT}/project/runs/${RUN_ID}/splat/patches"' in worker
    assert '-path "*/selected_images/*" -type l -delete' in worker


def test_stage1_upload_preserves_inner_scientific_run_without_following_links() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")

    assert '"${WORKER_MODE}" == "stage1_sfm_eval"' in worker
    assert 'scientific_runs/${scientific_run_id}/' in worker
    assert "--no-follow-symlinks" in worker
    assert 'find "${eval_datasets_root}" -type l -delete' in worker
    assert "Scientific-run upload verification found differences" in worker


def test_stage2_source_recovery_uses_the_undistortion_only_entrypoint() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")

    assert '"${WORKER_MODE}" == "stage2_source_recovery"' in worker
    assert "source_job_args+=(--recover-undistortion-only)" in worker


def test_stage2_worker_restores_only_requested_and_full_resolution_source_trees() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")

    assert 'TRAINING_WORKSPACE="undistorted_2048"' in worker
    assert '--exclude "*"' in worker
    assert '--include "sfm/${TRAINING_WORKSPACE}/*"' in worker
    assert '--include "sfm/undistorted_full_resolution/*"' in worker
    assert 'included_prefixes=[' in worker
    assert 'if [[ -L "${DATASET_DIR}/raw_images" ]]' in worker
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


def test_production_worker_uses_normal_pipeline_and_fixed_scientific_settings() -> None:
    worker = (REPO_ROOT / "scripts" / "nebius" / "run_worker.sh").read_text(encoding="utf-8")
    launcher = (REPO_ROOT / "scripts" / "nebius" / "launch_production_job.sh").read_text(encoding="utf-8")

    assert 'elif [[ "${WORKER_MODE}" == "production" ]]' in worker
    assert 'run_pipeline "splat.patch"' in worker
    assert 'run_pipeline "splat.train"' in worker
    assert "experiments/ablations/ablation_experiment.py" not in worker[worker.index("run_production()"):worker.index('if [[ "${WORKER_MODE}" == "stage2_source"')]
    assert "--advanced.splat.patching.max_cameras 200" in worker
    assert "--advanced.splat.train.num_iters 30000" in worker
    assert "--advanced.splat.train.num_splats_per_patch 2000000" in worker
    assert '--advanced.splat.train.max_width 2048' in worker
    assert '--advanced.splat.train.retry_max_width "[]"' in worker
    assert '--advanced.splat.train.retrain_failed "${PRODUCTION_RETRAIN_FAILED}"' in worker
    assert '--advanced.splat.train.patch_ids "${PRODUCTION_PATCH_IDS}"' in worker
    assert '"completed_iterations") != 30000' in worker
    assert '"final_splat_count") != 2000000' in worker
    assert "ply_vertex_count(output) != 2000000" in worker
    assert "verify_production_upload" in worker
    assert 'output.is_relative_to(container_run)' in worker
    assert "python3 - \"${run_dir}\" <<'PY' || return 1" in worker
    assert "production_complete.json" in worker
    assert "Refusing to reuse non-empty production prefix" in launcher
