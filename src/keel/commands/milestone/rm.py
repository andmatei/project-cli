"""`keel milestone rm <id>`."""
from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import edit_milestones, find_milestone
from keel.output import Output
from keel.prompts import confirm_destructive
from keel.workspace import resolve_cli_scope


def cmd_rm(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirm prompt."),
    force: bool = typer.Option(
        False, "--force", help="Remove even if not in cancelled state and even if tasks reference it."
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a milestone. Only allowed when status is 'cancelled' (or with --force)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
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

        confirm_destructive(f"Remove milestone {id}?", yes=yes)

        manifest.milestones = [m for m in manifest.milestones if m.id != id]

    out.result({"removed": id}, human_text=f"Milestone removed: {id}")
