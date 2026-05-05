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
    deliverable: str | None = None

    @property
    def unit_dir(self) -> Path:
        if self.project is None:
            raise ValueError("Scope has no project; cannot resolve unit_dir")
        if self.deliverable:
            return deliverable_dir(self.project, self.deliverable)
        return project_dir(self.project)

    # === Manifests at the unit root (was: under design/) ===

    @property
    def manifest_path(self) -> Path:
        return self.unit_dir / "project.toml"

    @property
    def milestones_manifest_path(self) -> Path:
        return self.unit_dir / "milestones.toml"

    # === Human-authored content at the unit root ===

    @property
    def scope_md_path(self) -> Path:
        return self.unit_dir / "scope.md"

    @property
    def design_md_path(self) -> Path:
        return self.unit_dir / "design.md"

    @property
    def readme_path(self) -> Path:
        return self.unit_dir / "README.md"

    @property
    def decisions_dir(self) -> Path:
        return self.unit_dir / "decisions"

    @property
    def plans_dir(self) -> Path:
        return self.unit_dir / "plans"

    @property
    def specs_dir(self) -> Path:
        return self.unit_dir / "specs"

    # === Tool state under .keel/ ===

    @property
    def keel_dir(self) -> Path:
        return self.unit_dir / ".keel"

    @property
    def phase_path(self) -> Path:
        return self.keel_dir / "phase"

    @property
    def lifecycle_lock_path(self) -> Path:
        return self.keel_dir / "lifecycle.lock.toml"

    # === Backward-compat shim — still serves callers that haven't migrated yet.
    # Removed in 0.2.0. Returns the unit_dir, NOT the obsolete design/ subdir.

    @property
    def design_dir(self) -> Path:
        return self.unit_dir


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
    # TODO(plan8-task4.1): switch to the new layout once migration command lands.
    return (
        deliverable_dir(project_name, deliverable_name) / "design" / "deliverable.toml"
    ).is_file()


def project_exists(project_name: str) -> bool:
    """Check whether a project's manifest exists on disk."""
    # TODO(plan8-task4.1): switch to the new layout once migration command lands.
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


def read_phase(unit_or_design_dir: Path) -> str:
    """Read the current phase. Tolerates both new and legacy layouts.

    New layout: `<unit_dir>/.keel/phase`.
    Legacy (pre-0.1.0): `<dir>/.phase` — supports both `<unit>/design/.phase`
    and `<unit>/.phase` callers.
    """
    from keel.lifecycle import DEFAULT_PHASE

    new_path = unit_or_design_dir / ".keel" / "phase"
    legacy_path = unit_or_design_dir / ".phase"  # pre-0.1.0
    for p in (new_path, legacy_path):
        if p.is_file():
            text = p.read_text().strip()
            return text.splitlines()[0].strip() if text else DEFAULT_PHASE
    return DEFAULT_PHASE


def iter_projects() -> Iterator[tuple[str, ProjectManifest, str]]:
    """Yield (project_name, manifest, current_phase) for each project in PROJECTS_DIR.

    Skips entries that don't have a `design/project.toml`. Useful for cross-project
    tooling (status dashboards, exports, plugins).
    """
    # TODO(plan8-task4.1): detect new-layout projects (manifest at root) too.
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
    return Scope(project=project, deliverable=deliverable).decisions_dir


def design_dir(project: str, deliverable: str | None = None) -> Path:
    """Deprecated. Returns the unit dir for backward compatibility."""
    return Scope(project=project, deliverable=deliverable).unit_dir


def manifest_path(project: str, deliverable: str | None = None) -> Path:
    """Path to the manifest TOML file for the given scope."""
    return Scope(project=project, deliverable=deliverable).manifest_path


def phase_file(project: str, deliverable: str | None = None) -> Path:
    """Deprecated alias for the new phase_path."""
    return Scope(project=project, deliverable=deliverable).phase_path


def milestones_manifest_path(project: str, deliverable: str | None = None) -> Path:
    """Path to the milestones.toml file for the given scope."""
    return Scope(project=project, deliverable=deliverable).milestones_manifest_path
