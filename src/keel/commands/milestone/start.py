"""`keel milestone start <id>`."""
from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import load_milestones_manifest, save_milestones_manifest
from keel.output import Output
from keel.workspace import resolve_cli_scope


def cmd_start(
    ctx: typer.Context,
    id: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    reopen: bool = typer.Option(
        False, "--reopen", help="Allow re-opening a milestone that's already done."
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Start work on a milestone (planned -> active)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)

    milestone = next((m for m in manifest.milestones if m.id == id), None)
    if milestone is None:
        out.error(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)
        raise typer.Exit(code=1)

    if milestone.status == "planned" or (milestone.status == "done" and reopen):
        milestone.status = "active"
    else:
        out.error(
            f"cannot start milestone in status '{milestone.status}' "
            f"(use --reopen to re-open a done milestone)",
            code=ErrorCode.INVALID_STATE,
        )
        raise typer.Exit(code=1)

    save_milestones_manifest(path, manifest)
    out.result(milestone.model_dump(), human_text=f"Milestone started: {id}")
