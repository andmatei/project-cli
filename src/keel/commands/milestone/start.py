"""`keel milestone start <id>`."""

from __future__ import annotations

import typer

from keel.api import ErrorCode, Output, edit_milestones, find_milestone, resolve_cli_scope


def cmd_start(
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
    reopen: bool = typer.Option(
        False, "--reopen", help="Allow re-opening a milestone that's already done."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Start work on a milestone (planned -> active)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)

    with edit_milestones(scope) as manifest:
        milestone = find_milestone(manifest, id)
        if milestone is None:
            out.fail(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)

        if milestone.status == "planned" or (milestone.status == "done" and reopen):
            milestone.status = "active"
        else:
            out.error(
                f"cannot start milestone in status '{milestone.status}' "
                f"(use --reopen to re-open a done milestone)",
                code=ErrorCode.INVALID_STATE,
            )
            raise typer.Exit(code=1)

    out.result(milestone.model_dump(), human_text=f"Milestone started: {id}")
