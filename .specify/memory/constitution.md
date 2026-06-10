<!--
Sync Impact Report
- Version change: 2.0.0 -> 2.1.0
- Modified principles: removed Spec Kit process guidance; retained only project-specific rules
- Modified principles: III. Explicit Resume And Overwrite Behaviour
- Added sections: none
- Removed sections: Development Workflow, Governance
- Templates reviewed: spec-template.md, plan-template.md, tasks-template.md; no changes required
- Follow-up TODOs: none
-->
# 3DReefs Constitution

## Core Principles

### I. Reproducible Pipeline Runs
The pipeline MUST provide one primary `uv` CLI entrypoint that runs from a config file and records the effective config, CLI overrides, tool versions, and run manifest for every run. Public example configs MUST use placeholders rather than private local paths.

### II. Observable Long-Running Work
SfM, patching, splatting, cleanup, compression, and merge stages MUST record stage timings, command output, warnings, completion status, and final artefact selection. A completed run must make it clear what happened, how long each stage took, and which parameters produced each output.

### III. Explicit Resume And Overwrite Behaviour
The pipeline MUST detect prior partial outputs before continuing. It MUST warn when config values changed between runs, and it MUST require explicit user intent before overwriting expensive or destructive outputs. Resume, overwrite, and already-completed-step decisions MUST be gathered during preflight before any requested step starts; mid-run prompts are allowed only for genuinely unforeseeable conditions that cannot be checked up front.

### IV. Modular, Testable Implementation
Reusable pipeline behaviour MUST live in importable modules under `src/`; CLI files, scripts, and experiment wrappers must stay thin. Config parsing, path resolution, command construction, status detection, output selection, and resume logic MUST have focused automated tests.

### V. External Tool Validation
COLMAP, LichtFeld Studio, and related external tools MUST be explicitly configured and validated before heavy work begins. Requested backends or GPU-capable stages MUST fail clearly when unavailable rather than silently falling back to a different tool or mode.

### VI. Data Safety
The pipeline MUST NOT modify raw input images in place. Public repo files MUST NOT contain secrets, credentials, private dataset paths, private server names, or machine-specific absolute paths except safe placeholders.

**Version**: 2.1.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-10
