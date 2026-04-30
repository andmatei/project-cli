"""`keel milestone add <id> --title "..."`."""

from __future__ import annotations

import typer

from keel.dryrun import OpLog
from keel.errors import ErrorCode
from keel.manifest import (
    Milestone,
    load_milestones_manifest,
    save_milestones_manifest,
)
from keel.output import Output
from keel.workspace import resolve_cli_scope


def cmd_add(
    ctx: typer.Context,
    id: str = typer.Argument(..., help="Milestone identifier (e.g., 'm1', 'foundation')."),
    title: str = typer.Option(..., "--title", help="Human-readable milestone title."),
    description: str = typer.Option("", "--description", help="Optional description."),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable", help="Scope: a deliverable."),
    project: str | None = typer.Option(None, "--project", "-p", help="Project name. Auto-detected from CWD."),
    no_push: bool = typer.Option(
        False, "--no-push",
        help="Skip pushing to the configured ticketing provider for this invocation.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print intended operations and exit."),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
) -> None:
    """Create a new milestone in the current scope's `milestones.toml`."""
    out = Output.from_context(ctx, json_mode=json_mode)

    scope = resolve_cli_scope(project, deliverable, out=out)
    path = scope.milestones_manifest_path

    manifest = load_milestones_manifest(path)
    if any(m.id == id for m in manifest.milestones):
        out.error(f"milestone with id '{id}' already exists in {path}", code=ErrorCode.EXISTS)
        raise typer.Exit(code=1)

    new_milestone = Milestone(id=id, title=title, description=description)

    if dry_run:
        log = OpLog()
        log.create_file(path, size=0) if not path.exists() else None
        log.modify_file(path)
        out.info(log.format_summary())
        return

    manifest.milestones.append(new_milestone)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_milestones_manifest(path, manifest)

    payload = new_milestone.model_dump()
    out.result(
        payload,
        human_text=f"Milestone created: {id}",
    )
