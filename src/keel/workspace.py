"""Workspace paths and CWD-based scope detection."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


def projects_dir() -> Path:
    """Root of the workspace. `$PROJECTS_DIR` overrides `~/projects`."""
    raw = os.environ.get("PROJECTS_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "projects").resolve()


def project_dir(name: str) -> Path:
    return projects_dir() / name


def deliverable_dir(project_name: str, deliverable_name: str) -> Path:
    return project_dir(project_name) / "deliverables" / deliverable_name


@dataclass(frozen=True)
class Scope:
    project: str | None
    deliverable: str | None


def detect_scope(cwd: Path | None = None) -> Scope:
    """Determine the (project, deliverable) scope from CWD.

    Returns Scope(None, None) if CWD is outside the workspace.
    """
    cwd_resolved = (cwd or Path.cwd()).resolve()
    root = projects_dir()
    try:
        rel = cwd_resolved.relative_to(root)
    except ValueError:
        return Scope(project=None, deliverable=None)
    parts = rel.parts
    if not parts:
        return Scope(project=None, deliverable=None)
    project = parts[0]
    deliverable = None
    if len(parts) >= 3 and parts[1] == "deliverables":
        deliverable = parts[2]
    return Scope(project=project, deliverable=deliverable)


def deliverable_exists(project_name: str, deliverable_name: str) -> bool:
    """Check whether a deliverable's manifest exists on disk."""
    return (deliverable_dir(project_name, deliverable_name) / "design" / "deliverable.toml").is_file()


def project_exists(project_name: str) -> bool:
    """Check whether a project's manifest exists on disk."""
    return (project_dir(project_name) / "design" / "project.toml").is_file()


def resolve_scope_or_fail(cwd: Path | None = None) -> Scope:
    """Like detect_scope, but verifies the scope's manifests exist on disk.

    Raises typer.Exit(1) with a clear message if:
    - No project is detected from CWD, OR
    - The detected project's manifest doesn't exist, OR
    - The detected deliverable's manifest doesn't exist.
    """
    import typer  # local import to keep workspace.py lightweight when imported in non-CLI contexts
    scope = detect_scope(cwd)
    if scope.project is None:
        typer.echo("error: no project detected from current directory", err=True)
        raise typer.Exit(code=1)
    if not project_exists(scope.project):
        typer.echo(f"error: project not found: {scope.project}", err=True)
        raise typer.Exit(code=1)
    if scope.deliverable is not None and not deliverable_exists(scope.project, scope.deliverable):
        typer.echo(
            f"error: deliverable not found: {scope.project}/{scope.deliverable}",
            err=True,
        )
        raise typer.Exit(code=1)
    return scope
