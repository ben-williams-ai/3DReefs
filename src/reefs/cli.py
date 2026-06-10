"""Command-line interface for the 3DReefs pipeline foundation."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from reefs.config.loader import load_config
from reefs.config.models import ResumePolicy
from reefs.config.overrides import apply_overrides, parse_unknown_overrides
from reefs.io.paths import derive_project_paths
from reefs.io.yaml_json import write_json, write_yaml
from reefs.logging.timings import TimingRecorder
from reefs.preflight.images import detect_image_layout, validate_recoloured_mirror
from reefs.preflight.tools import validate_tool
from reefs.preflight.validation import (
    PreflightResult,
    start_run_log,
    write_foundation_records,
    write_preflight_report,
)
from reefs.runs.manifest import build_cli_overrides_record, build_manifest, create_run_paths
from reefs.runs.resume import (
    build_config_diff_event,
    build_resume_event,
    discover_partial_runs,
)
from reefs.runs.status import RunStatus

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
@click.pass_context
def run(
    ctx: click.Context,
    config_path: Path,
    project_dir: Path | None,
    steps: str | None,
    resume_policy: str,
) -> None:
    """Run the Feature 1 foundation preflight."""
    selected_resume_policy = ResumePolicy(resume_policy)
    timings = TimingRecorder()
    status = RunStatus()

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

    run_paths = create_run_paths(derived_paths.runs)
    logger = start_run_log(run_paths)
    tool_results: list[dict[str, object]] = []
    try:
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

        result = PreflightResult(
            image_layout=layout,
            tool_results=tool_results,
            resume_events=resume_events,
            config_diff_events=config_diff_events,
        )
        with timings.stage("write_run_records"):
            status.complete_stage("foundation")
            status.finish("complete")
            cli_overrides_record = build_cli_overrides_record(
                overrides=accepted_overrides,
                project_dir_override=project_dir,
                requested_steps=requested_steps if steps else None,
                resume_policy=selected_resume_policy.value,
            )
            manifest = build_manifest(
                run_paths=run_paths,
                source_config_path=config_path.resolve(),
                project_dir=derived_paths.project_dir,
                requested_steps=requested_steps,
                tool_versions={item["tool_name"]: item for item in tool_results},
                resume_events=resume_events,
                config_diff_events=config_diff_events,
            )
            write_preflight_report(
                run_paths.preflight_report,
                derived_paths=derived_paths,
                requested_steps=requested_steps,
                result=result,
            )
            write_foundation_records(
                run_paths=run_paths,
                effective_config_data=effective_data,
                cli_overrides_record=cli_overrides_record,
                manifest=manifest,
                status=status,
                timings=timings,
            )
        write_json(run_paths.timings, timings.as_dict())
        logger.info("Foundation preflight completed")
        click.echo(f"Foundation checks completed: {run_paths.run_dir}")
    except Exception as exc:
        status.fail(str(exc))
        result = PreflightResult(
            image_layout=layout,
            tool_results=tool_results,
            resume_events=resume_events,
            config_diff_events=config_diff_events,
        )
        cli_overrides_record = build_cli_overrides_record(
            overrides=accepted_overrides,
            project_dir_override=project_dir,
            requested_steps=requested_steps if steps else None,
            resume_policy=selected_resume_policy.value,
        )
        manifest = build_manifest(
            run_paths=run_paths,
            source_config_path=config_path.resolve(),
            project_dir=derived_paths.project_dir,
            requested_steps=requested_steps,
            tool_versions={item["tool_name"]: item for item in tool_results},
            resume_events=resume_events,
            config_diff_events=config_diff_events,
        )
        write_preflight_report(
            run_paths.preflight_report,
            derived_paths=derived_paths,
            requested_steps=requested_steps,
            result=result,
        )
        write_foundation_records(
            run_paths=run_paths,
            effective_config_data=effective_data,
            cli_overrides_record=cli_overrides_record,
            manifest=manifest,
            status=status,
            timings=timings,
        )
        write_json(run_paths.timings, timings.as_dict())
        _exit_with_error(str(exc))


app = run
