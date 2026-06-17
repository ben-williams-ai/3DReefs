"""Command-line interface for the 3DReefs pipeline foundation."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from reefs.config.loader import load_config
from reefs.config.models import ResumePolicy
from reefs.config.overrides import apply_overrides, parse_unknown_overrides
from reefs.io.paths import derive_project_paths
from reefs.logging.terminal import TerminalReporter
from reefs.logging.timings import TimingRecorder
from reefs.preflight.images import detect_image_layout, validate_recoloured_mirror
from reefs.preflight.sfm import validate_sfm_preflight
from reefs.preflight.splat import validate_splat_preflight
from reefs.preflight.tools import validate_tool
from reefs.preflight.validation import start_run_log
from reefs.runs.manifest import build_cli_overrides_record, build_manifest, create_run_paths
from reefs.runs.recorder import RunRecorder
from reefs.runs.resume import (
    build_config_diff_event,
    build_resume_event,
    discover_partial_runs,
)
from reefs.runs.status import RunStatus
from reefs.sfm.pipeline import run_sfm_pipeline
from reefs.sfm.resume import inspect_sfm_outputs
from reefs.sfm.validation import wants_sfm
from reefs.splat.pipeline import run_splat_pipeline
from reefs.splat.validation import wants_splat

CONTEXT_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


def _parse_steps(steps: str | None) -> list[str]:
    if not steps:
        return ["foundation"]
    parsed = [step.strip() for step in steps.split(",") if step.strip()]
    if not parsed:
        raise click.BadParameter("--steps must contain at least one step")
    return parsed


def _effective_config_data(config, derived_paths) -> dict[str, object]:
    data = config.model_dump(mode="json")
    data["derived_paths"] = {
        "project_dir": str(derived_paths.project_dir),
        "raw_images": str(derived_paths.raw_images),
        "recoloured_images": str(derived_paths.recoloured_images),
        "runs": str(derived_paths.runs),
    }
    return data


def _resolve_resume_decisions(
    *,
    partials,
    requested_config: dict[str, object],
    resume_policy: ResumePolicy,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    resume_events: list[dict[str, object]] = []
    config_diff_events: list[dict[str, object]] = []
    if not partials:
        return resume_events, config_diff_events

    interactive = sys.stdin.isatty()
    if resume_policy == ResumePolicy.FAIL:
        raise ValueError("Prior partial outputs require a decision")
    if resume_policy == ResumePolicy.PROMPT and not interactive:
        raise ValueError(
            "Prior partial outputs detected in a non-interactive run. "
            "Supply --resume-policy resume, overwrite, or fail."
        )

    for partial in partials:
        if resume_policy == ResumePolicy.RESUME:
            decision = "continue"
            source = "resume_policy"
        elif resume_policy == ResumePolicy.OVERWRITE:
            decision = "overwrite"
            source = "resume_policy"
        else:
            message = (
                f"Previous run {partial.run_dir.name} has status "
                f"{(partial.status or {}).get('status', 'unknown')} for step {partial.step}. "
                "Continue/resume it?"
            )
            decision = "continue" if click.confirm(message, default=False) else "overwrite"
            source = "interactive_prompt"
        resume_events.append(build_resume_event(partial=partial, decision=decision, source=source))
        diff_event = build_config_diff_event(
            partial=partial,
            requested_config=requested_config,
            decision=decision,
            interactive=interactive,
        )
        if diff_event:
            config_diff_events.append(diff_event)
    return resume_events, config_diff_events


def _selected_resume_run_id(resume_events: list[dict[str, object]]) -> str | None:
    """Return the prior run id to reuse when the decision is unambiguous."""
    if not resume_events:
        return None
    run_ids = {str(event.get("previous_run_id")) for event in resume_events}
    decisions = {str(event.get("decision")) for event in resume_events}
    if len(run_ids) == 1 and decisions <= {"continue", "overwrite"}:
        return next(iter(run_ids))
    return None


def _has_sfm_work_after_preflight(requested_steps: list[str]) -> bool:
    """Return whether requested SfM steps include heavyweight work."""
    return any(step == "sfm" or (step.startswith("sfm.") and step != "sfm.preflight") for step in requested_steps)


def _final_completed_stage(
    *,
    requested_steps: list[str],
    sfm_result: object | None,
    sfm_preflight_result: object | None,
    splat_result: object | None,
    splat_preflight_result: object | None,
) -> str:
    """Return the most specific successful completion label."""
    if splat_result:
        if "splat" in requested_steps:
            return "splat"
        for step in reversed(requested_steps):
            if step.startswith("splat."):
                return step
        return "splat"
    if splat_preflight_result:
        return "splat.preflight"
    if sfm_result:
        if "sfm" in requested_steps:
            return "sfm"
        for step in reversed(requested_steps):
            if step.startswith("sfm."):
                return step
        return "sfm"
    if sfm_preflight_result:
        return "sfm.preflight"
    return "foundation"


def _completion_message(final_stage: str) -> str:
    """Return a concise user-facing completion message for a successful run."""
    if final_stage == "foundation":
        return "Foundation checks completed"
    if final_stage.endswith(".preflight"):
        return f"{final_stage} completed"
    if final_stage in {"sfm", "splat"}:
        return f"{final_stage} pipeline completed"
    return f"{final_stage} completed"


def _prime_status_from_filesystem(status: RunStatus, run_dir: Path) -> dict[str, dict[str, object]]:
    """Seed status from existing outputs in a resumed run directory."""
    detected = inspect_sfm_outputs(run_dir)
    stage_order = [
        "sfm.intrinsics",
        "sfm.extract",
        "sfm.feature_extraction",
        "sfm.matching",
        "sfm.reconstruction",
        "sfm.undistort",
    ]
    for stage, details in detected.items():
        state = str(details.get("state", "unknown"))
        status.stage_statuses[stage] = state
        if stage == "sfm.feature_extraction":
            status.stage_statuses["sfm.extract"] = state
    for stage in stage_order:
        if status.stage_statuses.get(stage) == "complete":
            status.last_completed_stage = stage
    return detected


def _exit_with_error(message: str) -> None:
    click.echo(f"Error: {message}", err=True)
    raise click.exceptions.Exit(1)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    help="Config YAML path.",
)
@click.option(
    "--project-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Override project.dir for this invocation.",
)
@click.option("--steps", default=None, help="Comma-separated pipeline steps to preflight.")
@click.option(
    "--resume-policy",
    type=click.Choice([policy.value for policy in ResumePolicy]),
    default=ResumePolicy.PROMPT.value,
    show_default=True,
    help="prompt, resume, overwrite, or fail.",
)
@click.option(
    "--run-id",
    default=None,
    help="Existing run id to resume or overwrite in place.",
)
@click.pass_context
def run(
    ctx: click.Context,
    config_path: Path,
    project_dir: Path | None,
    steps: str | None,
    resume_policy: str,
    run_id: str | None,
) -> None:
    """Run the Feature 1 foundation preflight."""
    selected_resume_policy = ResumePolicy(resume_policy)
    timings = TimingRecorder()
    status = RunStatus()
    recorder: RunRecorder | None = None
    logger = None
    reporter: TerminalReporter | None = None

    try:
        with timings.stage("load_config"):
            source_config = load_config(config_path)
        with timings.stage("apply_overrides"):
            override_records = parse_unknown_overrides(list(ctx.args))
            effective_config, accepted_overrides = apply_overrides(source_config, override_records)
        with timings.stage("derive_paths"):
            requested_steps = _parse_steps(steps)
            derived_paths = derive_project_paths(effective_config, project_dir)
            effective_data = _effective_config_data(effective_config, derived_paths)
        with timings.stage("validate_inputs"):
            layout = detect_image_layout(derived_paths.raw_images)
            if effective_config.project.recolour_images:
                validate_recoloured_mirror(
                    raw_images=derived_paths.raw_images,
                    recoloured_images=derived_paths.recoloured_images,
                    layout=layout,
                )
        with timings.stage("detect_partial_runs"):
            partials = discover_partial_runs(derived_paths.runs, requested_steps)
            resume_events, config_diff_events = _resolve_resume_decisions(
                partials=partials,
                requested_config=effective_data,
                resume_policy=selected_resume_policy,
            )
    except Exception as exc:
        _exit_with_error(str(exc))

    selected_run_id = run_id or _selected_resume_run_id(resume_events)
    try:
        run_paths = create_run_paths(derived_paths.runs, run_id=selected_run_id)
    except Exception as exc:
        _exit_with_error(str(exc))
    detected_existing_outputs = _prime_status_from_filesystem(status, run_paths.run_dir) if selected_run_id else {}
    cli_overrides_record = build_cli_overrides_record(
        overrides=accepted_overrides,
        project_dir_override=project_dir,
        requested_steps=requested_steps if steps else None,
        resume_policy=selected_resume_policy.value,
        run_id=selected_run_id,
    )
    manifest = build_manifest(
        run_paths=run_paths,
        source_config_path=config_path.resolve(),
        project_dir=derived_paths.project_dir,
        requested_steps=requested_steps,
        tool_versions={},
        resume_events=resume_events,
        config_diff_events=config_diff_events,
    )
    if detected_existing_outputs:
        manifest["detected_existing_outputs"] = detected_existing_outputs
    recorder = RunRecorder(
        run_paths=run_paths,
        effective_config_data=effective_data,
        cli_overrides_record=cli_overrides_record,
        manifest=manifest,
        status=status,
        timings=timings,
    )
    recorder.write_all()
    logger = start_run_log(
        run_paths,
        message=f"Pipeline run started ({'resume' if selected_run_id else 'new'} run {run_paths.run_id})",
    )
    reporter = TerminalReporter(logger=logger)
    recorder.reporter = reporter
    reporter.tee_line(f"Pipeline run started ({'resume' if selected_run_id else 'new'} run {run_paths.run_id})")
    tool_results: list[dict[str, object]] = []
    try:
        recorder.stage_started("foundation.validate_tools")
        with timings.stage("validate_tools"):
            checks = [
                validate_tool(
                    tool_name="COLMAP",
                    binary=effective_config.tools.colmap_bin,
                    target_version="4.0.4",
                    version_args=["-h"],
                ),
                validate_tool(
                    tool_name="LichtFeld Studio",
                    binary=effective_config.tools.lfs_bin,
                    target_version="v0.5.2",
                ),
            ]
            if effective_config.advanced.splat.sog.enabled:
                checks.append(
                    validate_tool(
                        tool_name="SOG conversion",
                        binary=effective_config.tools.splat_transform_bin,
                        target_version=None,
                    )
                )
            tool_results = [check.as_dict() for check in checks]
            failures = [result for result in tool_results if result["status"] != "passed"]
            if failures:
                for failure in failures:
                    logger.warning(str(failure["message"]))
                raise RuntimeError("; ".join(str(failure["message"]) for failure in failures))
        recorder.stage_completed("foundation.validate_tools")
        recorder.update_manifest(tool_versions={item["tool_name"]: item for item in tool_results})

        sfm_preflight_result = None
        sfm_result = None
        splat_preflight_result = None
        splat_result = None
        if wants_sfm(requested_steps):
            recorder.stage_started("sfm.preflight")
            with timings.stage("sfm.preflight"):
                sfm_preflight_result = validate_sfm_preflight(
                    config=effective_config,
                    derived_paths=derived_paths,
                    layout=layout,
                    run_paths=run_paths,
                )
                for warning in sfm_preflight_result.warnings:
                    logger.warning(warning)
                status.warnings_count += len(sfm_preflight_result.warnings)
            recorder.stage_completed("sfm.preflight")
            recorder.update_manifest(sfm_preflight=sfm_preflight_result.as_dict())
            if _has_sfm_work_after_preflight(requested_steps):
                sfm_result = run_sfm_pipeline(
                    config=effective_config,
                    derived_paths=derived_paths,
                    layout=layout,
                    run_paths=run_paths,
                    preflight_result=sfm_preflight_result,
                    requested_steps=requested_steps,
                    timings=timings,
                    recorder=recorder,
                    resume_policy=selected_resume_policy,
                )
                new_warnings = [
                    warning
                    for warning in sfm_result.warnings
                    if sfm_preflight_result is None or warning not in sfm_preflight_result.warnings
                ]
                for warning in new_warnings:
                    logger.warning(warning)
                status.warnings_count += len(new_warnings)
                recorder.update_manifest(sfm=sfm_result.as_dict())

        if wants_splat(requested_steps):
            recorder.stage_started("splat.preflight")
            with timings.stage("splat.preflight"):
                splat_preflight_result = validate_splat_preflight(
                    config=effective_config,
                    run_paths=run_paths,
                    requested_steps=requested_steps,
                    resume_policy=selected_resume_policy,
                )
                for warning in splat_preflight_result.warnings:
                    logger.warning(warning)
                status.warnings_count += len(splat_preflight_result.warnings)
            recorder.stage_completed("splat.preflight")
            recorder.update_manifest(splat_preflight=splat_preflight_result.as_dict())
            if any(step == "splat" or (step.startswith("splat.") and step != "splat.preflight") for step in requested_steps):
                splat_result = run_splat_pipeline(
                    config=effective_config,
                    preflight_result=splat_preflight_result,
                    requested_steps=requested_steps,
                    timings=timings,
                    recorder=recorder,
                )
                for warning in splat_result.warnings:
                    logger.warning(warning)
                status.warnings_count += len(splat_result.warnings)
                recorder.update_manifest(splat=splat_result.as_dict())
                postprocess_warnings = []
                if splat_result.postprocess:
                    postprocess_warnings = list(splat_result.postprocess.get("warnings", []))
                if postprocess_warnings:
                    click.echo("Post-processing warnings:")
                    for warning in postprocess_warnings:
                        click.echo(f"- {warning}")

        with timings.stage("write_run_records"):
            final_stage = _final_completed_stage(
                requested_steps=requested_steps,
                sfm_result=sfm_result,
                sfm_preflight_result=sfm_preflight_result,
                splat_result=splat_result,
                splat_preflight_result=splat_preflight_result,
            )
            status.complete_stage(final_stage)
            status.finish("complete")
            recorder.write_all()
        message = _completion_message(final_stage)
        logger.info(message)
        click.echo(f"{message}: {run_paths.run_dir}")
    except KeyboardInterrupt as exc:
        if recorder:
            recorder.stage_interrupted(status.current_stage or "pipeline", "Run interrupted by user or host process")
            recorder.write_all()
        elif reporter:
            reporter.stage_interrupted("pipeline", "Run interrupted by user or host process")
        elif logger:
            logger.warning("Run interrupted before completion")
        _exit_with_error(str(exc) or "Run interrupted")
    except Exception as exc:
        if recorder:
            recorder.stage_failed(status.current_stage or "pipeline", str(exc))
            recorder.write_all()
        else:
            status.fail(str(exc))
        _exit_with_error(str(exc))


app = run
