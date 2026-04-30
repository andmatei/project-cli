"""`keel milestone cancel <id>`."""
from __future__ import annotations

import typer

from keel.api import ErrorCode, Output, confirm_destructive, edit_milestones, find_milestone
from keel.workspace import resolve_cli_scope


def cmd_cancel(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirm prompt."),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Cancel a milestone (any state -> cancelled)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        milestone = find_milestone(manifest, id)
        if milestone is None:
            out.fail(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)

        confirm_destructive(f"Cancel milestone {id} (currently {milestone.status})?", yes=yes)

        milestone.status = "cancelled"

    out.result(milestone.model_dump(), human_text=f"Milestone cancelled: {id}")
