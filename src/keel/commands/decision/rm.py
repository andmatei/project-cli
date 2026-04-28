"""`keel decision rm <slug>`."""
from __future__ import annotations
from pathlib import Path
import typer

from keel import workspace
from keel.commands.decision.show import _find_decision
from keel.output import Output
from keel.prompts import confirm_destructive


def cmd_rm(
    slug: str = typer.Argument(...),
    deliverable: str | None = typer.Option(None, "-D", "--deliverable"),
    project: str | None = typer.Option(None, "--project", "-p"),
    yes: bool = typer.Option(False, "-y", "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a decision file (the typical 'changed my mind' pattern is `decision new --supersedes` instead)."""
    out = Output(json_mode=json_mode)

    if project is None:
        scope = workspace.detect_scope()
        project = scope.project
        deliverable = deliverable if deliverable is not None else scope.deliverable
    if project is None:
        out.error("no project specified and none detected from CWD", code="no_project")
        raise typer.Exit(code=1)

    if deliverable:
        target_dir = workspace.deliverable_dir(project, deliverable) / "design" / "decisions"
    else:
        target_dir = workspace.project_dir(project) / "design" / "decisions"

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
