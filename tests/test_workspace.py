"""Tests for workspace path conventions and CWD scope detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from keel.workspace import (
    Scope,
    deliverable_dir,
    detect_scope,
    project_dir,
    projects_dir,
)


def test_projects_dir_default_is_home_projects(monkeypatch) -> None:
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    assert projects_dir() == Path.home() / "projects"


def test_projects_dir_honors_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    assert projects_dir() == tmp_path


def test_project_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    assert project_dir("foo") == tmp_path / "foo"


def test_deliverable_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    assert deliverable_dir("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar"


def test_detect_scope_outside_projects(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path.parent)
    assert detect_scope() == Scope(project=None, deliverable=None)


def test_detect_scope_in_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo")
    assert detect_scope() == Scope(project="foo", deliverable=None)


def test_detect_scope_in_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "deliverables" / "bar").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "deliverables" / "bar")
    assert detect_scope() == Scope(project="foo", deliverable="bar")


def test_detect_scope_in_project_subdir(monkeypatch, tmp_path) -> None:
    """Scope detection works from any subdir, not just design/."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "code").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "code")
    assert detect_scope() == Scope(project="foo", deliverable=None)


def test_deliverable_exists_true(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "deliverables" / "bar").mkdir(parents=True)
    (tmp_path / "foo" / "deliverables" / "bar" / "project.toml").write_text(
        '[project]\nname = "bar"\ndescription = "d"\ncreated = 2026-04-28\nshared_worktree = false\n'
    )
    from keel.workspace import deliverable_exists

    assert deliverable_exists("foo", "bar") is True


def test_deliverable_exists_false(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import deliverable_exists

    assert deliverable_exists("foo", "bar") is False


def test_resolve_cli_scope_explicit_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo").mkdir(parents=True)
    (tmp_path / "foo" / "project.toml").write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-28\n'
    )
    from keel.workspace import resolve_cli_scope

    scope = resolve_cli_scope(project="foo", deliverable=None)
    assert scope.project == "foo"
    assert scope.deliverable is None


def test_resolve_cli_scope_falls_back_to_cwd(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo").mkdir(parents=True)
    (tmp_path / "foo" / "project.toml").write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-28\n'
    )
    monkeypatch.chdir(tmp_path / "foo")
    from keel.workspace import resolve_cli_scope

    scope = resolve_cli_scope(project=None)
    assert scope.project == "foo"


def test_resolve_cli_scope_missing_project_exits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    import typer

    from keel.workspace import resolve_cli_scope

    with pytest.raises(typer.Exit) as exc:
        resolve_cli_scope(project=None)
    assert exc.value.exit_code == 1


def test_resolve_cli_scope_unknown_project_exits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    import typer

    from keel.workspace import resolve_cli_scope

    with pytest.raises(typer.Exit) as exc:
        resolve_cli_scope(project="ghost")
    assert exc.value.exit_code == 1


def test_read_phase_default_when_missing(tmp_path) -> None:
    from keel.workspace import read_phase

    assert read_phase(tmp_path) == "scoping"


def test_read_phase_default_when_empty(tmp_path) -> None:
    (tmp_path / ".phase").write_text("")
    from keel.workspace import read_phase

    assert read_phase(tmp_path) == "scoping"


def test_read_phase_value(tmp_path) -> None:
    (tmp_path / ".phase").write_text("implementing\n2026-04-28  scoping → implementing\n")
    from keel.workspace import read_phase

    assert read_phase(tmp_path) == "implementing"


def test_decisions_dir_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import decisions_dir

    assert decisions_dir("foo") == tmp_path / "foo" / "decisions"


def test_decisions_dir_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import decisions_dir

    assert decisions_dir("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar" / "decisions"


def test_design_dir_project(monkeypatch, tmp_path) -> None:
    """Backward-compat shim: design_dir() now returns the unit_dir."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import design_dir

    assert design_dir("foo") == tmp_path / "foo"


def test_design_dir_deliverable(monkeypatch, tmp_path) -> None:
    """Backward-compat shim: design_dir() now returns the unit_dir."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import design_dir

    assert design_dir("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar"


def test_manifest_path_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import manifest_path

    assert manifest_path("foo").name == "project.toml"


def test_manifest_path_deliverable(monkeypatch, tmp_path) -> None:
    """In the new layout, deliverables also use project.toml at the unit root."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import manifest_path

    assert manifest_path("foo", "bar").name == "project.toml"
    assert manifest_path("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar" / "project.toml"


def test_phase_file(monkeypatch, tmp_path) -> None:
    """phase_file() is a deprecated alias that now returns the .keel/phase path."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import phase_file

    assert phase_file("foo") == tmp_path / "foo" / ".keel" / "phase"
    assert phase_file("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar" / ".keel" / "phase"


def test_scope_unit_dir_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s = Scope(project="foo", deliverable=None)
    assert s.unit_dir == tmp_path / "foo"


def test_scope_unit_dir_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s = Scope(project="foo", deliverable="bar")
    assert s.unit_dir == tmp_path / "foo" / "deliverables" / "bar"


def test_scope_design_dir(monkeypatch, tmp_path) -> None:
    """Backward-compat shim: design_dir now equals the unit_dir."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s = Scope(project="foo", deliverable="bar")
    assert s.design_dir == tmp_path / "foo" / "deliverables" / "bar"


def test_scope_manifest_path(monkeypatch, tmp_path) -> None:
    """In the new layout, both projects and deliverables use project.toml."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s_proj = Scope(project="foo", deliverable=None)
    s_deliv = Scope(project="foo", deliverable="bar")
    assert s_proj.manifest_path.name == "project.toml"
    assert s_deliv.manifest_path.name == "project.toml"


def test_scope_phase_path(monkeypatch, tmp_path) -> None:
    """Renamed from .phase_file → .phase_path; lives under .keel/."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s = Scope(project="foo", deliverable=None)
    assert s.phase_path == tmp_path / "foo" / ".keel" / "phase"


def test_scope_decisions_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s = Scope(project="foo", deliverable="bar")
    assert s.decisions_dir == tmp_path / "foo" / "deliverables" / "bar" / "decisions"


def test_milestones_manifest_path_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import milestones_manifest_path

    assert milestones_manifest_path("foo").name == "milestones.toml"


def test_milestones_manifest_path_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import milestones_manifest_path

    assert milestones_manifest_path("foo", "bar").name == "milestones.toml"


def test_scope_milestones_manifest_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import Scope

    s_proj = Scope(project="foo", deliverable=None)
    s_deliv = Scope(project="foo", deliverable="bar")
    assert s_proj.milestones_manifest_path.name == "milestones.toml"
    assert s_deliv.milestones_manifest_path.name == "milestones.toml"


def test_iter_projects_empty(projects) -> None:
    from keel.workspace import iter_projects

    assert list(iter_projects()) == []


def test_iter_projects_yields_each(projects, make_project) -> None:
    from keel.workspace import iter_projects

    make_project("alpha")
    make_project("beta")
    items = list(iter_projects())
    names = {name for name, _, _ in items}
    assert names == {"alpha", "beta"}
    for _, manifest, phase in items:
        assert manifest.project.name in names
        assert phase == "scoping"  # default for fresh projects


# === New layout (Plan 8 / 0.1.0): manifests at root, .keel/ for state ===


def projects_scope(name: str):
    """Helper: build a Scope for a project name (no fixture import jiggling)."""
    from keel.workspace import Scope

    return Scope(project=name)


def test_scope_manifest_path_at_root(projects, make_project) -> None:
    """In the new layout, project.toml lives at <project>/project.toml."""
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.manifest_path == proj / "project.toml"


def test_scope_phase_path_in_keel_dir(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.phase_path == proj / ".keel" / "phase"


def test_scope_lifecycle_lock_path(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.lifecycle_lock_path == proj / ".keel" / "lifecycle.lock.toml"


def test_scope_keel_dir(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.keel_dir == proj / ".keel"


def test_scope_milestones_manifest_path_at_root(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.milestones_manifest_path == proj / "milestones.toml"


def test_scope_decisions_dir_at_root(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.decisions_dir == proj / "decisions"


def test_scope_human_design_files_at_root(projects, make_project) -> None:
    proj = make_project("foo")
    scope = projects_scope("foo")
    assert scope.scope_md_path == proj / "scope.md"
    assert scope.design_md_path == proj / "design.md"
