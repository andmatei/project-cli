"""`keel milestone rm <id>`."""
from __future__ import annotations

import typer

from keel.api import (
    ErrorCode,
    OpLog,
    Output,
    confirm_destructive,
    edit_milestones,
    find_milestone,
    load_milestones_manifest,
)
from keel.workspace import resolve_cli_scope


def cmd_rm(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(
        None, "-D", "--deliverable",
        help="Scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Project name. Auto-detected from CWD if omitted.",
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirm prompt."),
    force: bool = typer.Option(
        False, "--force", help="Remove even if not in cancelled state and even if tasks reference it."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print intended operations and exit; write nothing."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Remove a milestone. Only allowed when status is 'cancelled' (or with --force)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    # Pre-validate before write: load and validate conditions
    manifest = load_milestones_manifest(scope.milestones_manifest_path)
    milestone = find_milestone(manifest, id)
    if milestone is None:
        out.fail(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)

    if milestone.status != "cancelled" and not force:
        out.error(
            f"cannot remove milestone in status '{milestone.status}' "
            f"(only 'cancelled' allowed; use --force to override)",
            code=ErrorCode.INVALID_STATE,
        )
        raise typer.Exit(code=1)

    referencing = [t.id for t in manifest.tasks if t.milestone == id]
    if referencing and not force:
        out.error(
            f"cannot remove milestone '{id}'; tasks reference it: {', '.join(referencing)} "
            "(use --force to remove anyway)",
            code=ErrorCode.INVALID_STATE,
        )
        raise typer.Exit(code=1)

    if dry_run:
        log = OpLog()
        log.modify_file(scope.milestones_manifest_path)
        out.info(log.format_summary())
        return

    confirm_destructive(f"Remove milestone {id}?", yes=yes)

    with edit_milestones(scope) as manifest:
        manifest.milestones = [m for m in manifest.milestones if m.id != id]

    out.result({"removed": id}, human_text=f"Milestone removed: {id}")
