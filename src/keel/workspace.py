"""Workspace paths and CWD-based scope detection."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from keel.manifest import ProjectManifest
    from keel.output import Output


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

    @property
    def unit_dir(self) -> Path:
        if self.project is None:
            raise ValueError("Scope has no project; cannot resolve unit_dir")
        if self.deliverable:
            return deliverable_dir(self.project, self.deliverable)
        return project_dir(self.project)

    @property
    def design_dir(self) -> Path:
        return self.unit_dir / "design"

    @property
    def manifest_path(self) -> Path:
        if self.deliverable:
            return self.design_dir / "deliverable.toml"
        return self.design_dir / "project.toml"

    @property
    def phase_file(self) -> Path:
        return self.design_dir / ".phase"

    @property
    def decisions_dir(self) -> Path:
        return self.design_dir / "decisions"

    @property
    def milestones_manifest_path(self) -> Path:
        return self.design_dir / "milestones.toml"


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
    return (
        deliverable_dir(project_name, deliverable_name) / "design" / "deliverable.toml"
    ).is_file()


def project_exists(project_name: str) -> bool:
    """Check whether a project's manifest exists on disk."""
    return (project_dir(project_name) / "design" / "project.toml").is_file()


def resolve_cli_scope(
    project: str | None,
    deliverable: str | None = None,
    *,
    allow_deliverable: bool = True,
    require_deliverable: bool = False,
    out: Output | None = None,
) -> Scope:
    """Resolve the (project, deliverable) scope for a CLI command.

    Resolution order:
    1. If `project` is None, fall back to CWD detection.
    2. If `deliverable` is None and `allow_deliverable=True`, fall back to CWD detection for it too.
    3. Validate that the resolved project exists. Exit 1 with a clear message if not.
    4. If a deliverable is in scope, validate its manifest exists. Exit 1 if not.
    5. If `require_deliverable=True` and no deliverable resolved, exit 1.

    Always exits 1 (via typer.Exit) when scope can't be resolved.

    Args:
        out: Optional Output instance to route error messages through (JSON-mode aware).
             Defaults to a fresh plain Output() when not provided.
    """
    import typer

    from keel.errors import (
        HINT_LIST_DELIVERABLES,
        HINT_LIST_PROJECTS,
        HINT_PASS_PROJECT,
        ErrorCode,
    )
    from keel.output import Output as _Output

    _out = out if out is not None else _Output()

    if project is None:
        scope = detect_scope()
        project = scope.project
        if allow_deliverable and deliverable is None:
            deliverable = scope.deliverable
    if project is None:
        _out.error(
            f"no project specified and none detected from CWD\n  {HINT_PASS_PROJECT}",
            code=ErrorCode.NO_PROJECT,
        )
        raise typer.Exit(code=1)
    if not project_exists(project):
        _out.error(
            f"project not found: {project}\n  {HINT_LIST_PROJECTS}",
            code=ErrorCode.NOT_FOUND,
        )
        raise typer.Exit(code=1)
    if deliverable is not None and not deliverable_exists(project, deliverable):
        _out.error(
            f"deliverable not found: {project}/{deliverable}\n  {HINT_LIST_DELIVERABLES}",
            code=ErrorCode.NOT_FOUND,
        )
        raise typer.Exit(code=1)
    if require_deliverable and deliverable is None:
        _out.error("deliverable required for this command", code=ErrorCode.NOT_FOUND)
        raise typer.Exit(code=1)
    return Scope(project=project, deliverable=deliverable)


def read_phase(design_dir: Path) -> str:
    """Read the current phase from `<design_dir>/.phase`. Returns DEFAULT_PHASE if the file is missing or empty."""
    from keel.lifecycle import DEFAULT_PHASE

    phase_file_path = design_dir / ".phase"
    if not phase_file_path.is_file():
        return DEFAULT_PHASE
    lines = phase_file_path.read_text().splitlines()
    if not lines:
        return DEFAULT_PHASE
    return lines[0].strip() or DEFAULT_PHASE


def iter_projects() -> Iterator[tuple[str, ProjectManifest, str]]:
    """Yield (project_name, manifest, current_phase) for each project in PROJECTS_DIR.

    Skips entries that don't have a `design/project.toml`. Useful for cross-project
    tooling (status dashboards, exports, plugins).
    """
    pdir = projects_dir()
    if not pdir.is_dir():
        return
    for entry in sorted(pdir.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "design" / "project.toml"
        if not manifest_path.is_file():
            continue
        try:
            from keel.manifest import load_project_manifest

            manifest = load_project_manifest(manifest_path)
        except Exception:
            continue
        phase = read_phase(entry / "design")
        yield (entry.name, manifest, phase)


def decisions_dir(project: str, deliverable: str | None = None) -> Path:
    """Path to the decisions/ directory for the given scope."""
    if deliverable:
        return deliverable_dir(project, deliverable) / "design" / "decisions"
    return project_dir(project) / "design" / "decisions"


def design_dir(project: str, deliverable: str | None = None) -> Path:
    """Path to the design/ directory for the given scope."""
    if deliverable:
        return deliverable_dir(project, deliverable) / "design"
    return project_dir(project) / "design"


def manifest_path(project: str, deliverable: str | None = None) -> Path:
    """Path to the manifest TOML file for the given scope."""
    if deliverable:
        return design_dir(project, deliverable) / "deliverable.toml"
    return design_dir(project) / "project.toml"


def phase_file(project: str, deliverable: str | None = None) -> Path:
    """Path to the .phase file for the given scope."""
    return design_dir(project, deliverable) / ".phase"


def milestones_manifest_path(project: str, deliverable: str | None = None) -> Path:
    """Path to the milestones.toml file for the given scope."""
    return design_dir(project, deliverable) / "milestones.toml"
