"""`keel milestone cancel <id>`."""
from __future__ import annotations

import typer

from keel.errors import ErrorCode
from keel.manifest import load_milestones_manifest, save_milestones_manifest
from keel.output import Output
from keel.prompts import confirm_destructive
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
    path = scope.milestones_manifest_path
    manifest = load_milestones_manifest(path)

    milestone = next((m for m in manifest.milestones if m.id == id), None)
    if milestone is None:
        out.fail(f"no milestone with id '{id}'", code=ErrorCode.NOT_FOUND)

    confirm_destructive(f"Cancel milestone {id} (currently {milestone.status})?", yes=yes)

    milestone.status = "cancelled"
    save_milestones_manifest(path, manifest)
    out.result(milestone.model_dump(), human_text=f"Milestone cancelled: {id}")
