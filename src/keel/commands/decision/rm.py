"""`keel decision rm <slug>`."""

from __future__ import annotations

import typer

from keel import workspace
from keel.commands.decision.show import _find_decision
from keel.output import Output
from keel.prompts import confirm_destructive


def cmd_rm(
    ctx: typer.Context,
    slug: str = typer.Argument(..., help="Decision slug (date prefix optional) or full filename."),
    deliverable: str | None = typer.Option(
        None,
        "-D",
        "--deliverable",
        help="Decision scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Parent project. Auto-detected from CWD if omitted."
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="Skip interactive prompts (description, etc.)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print intended operations and exit; write nothing."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Remove a decision file (the typical 'changed my mind' pattern is `decision new --supersedes` instead)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    from keel.workspace import resolve_cli_scope

    scope = resolve_cli_scope(project, deliverable)
    project = scope.project
    deliverable = scope.deliverable

    target_dir = workspace.decisions_dir(project, deliverable)

    path = _find_decision(target_dir, slug)
    if path is None:
        out.error(f"decision not found: {slug}", code="not_found")
        raise typer.Exit(code=1)

    if dry_run:
        from keel.dryrun import OpLog

        log = OpLog()
        log.delete_file(path)
        out.info(log.format_summary())
        return

    confirm_destructive(f"Remove decision {path.name}?", yes=yes)

    path.unlink()
    out.info(f"Removed: {path}")
    out.result({"removed": str(path)}, human_text=f"Decision removed: {path}")
