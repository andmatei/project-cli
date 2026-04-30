"""`keel task rm <id>`."""

from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    OpLog,
    Output,
    confirm_destructive,
    edit_milestones,
    find_task,
    load_milestones_manifest,
)
from keel.workspace import resolve_cli_scope


def cmd_rm(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(
        None,
        "-D",
        "--deliverable",
        help="Scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Project name. Auto-detected from CWD if omitted.",
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirm prompt."),
    force: bool = typer.Option(
        False, "--force", help="Remove even if other tasks depend on this one."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Remove a task. Refuses if other tasks depend on it (use --force to override)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    # Pre-validate before write
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    task = find_task(manifest, id)
    if task is None:
        out.fail(f"no task with id '{id}'", code=ErrorCode.NOT_FOUND)

    dependents = [t.id for t in manifest.tasks if id in t.depends_on]
    if dependents and not force:
        out.error(
            f"cannot remove task '{id}'; depended on by: {', '.join(dependents)} "
            "(use --force to remove anyway)",
            code=ErrorCode.INVALID_STATE,
        )
        raise typer.Exit(code=1)

    if dry_run:
        log = OpLog()
        log.modify_file(scope.milestones_manifest_path)
        out.info(log.format_summary())
        return

    confirm_destructive(f"Remove task {id}?", yes=yes)

    with edit_milestones(scope) as manifest:
        manifest.tasks = [t for t in manifest.tasks if t.id != id]

    out.result({"removed": id}, human_text=f"Task removed: {id}")
