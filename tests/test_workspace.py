"""Tests for workspace path conventions and CWD scope detection."""
from __future__ import annotations
from pathlib import Path
import os
import pytest
from keel.workspace import (
    projects_dir,
    project_dir,
    deliverable_dir,
    detect_scope,
    Scope,
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
    (tmp_path / "foo" / "design").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "design")
    assert detect_scope() == Scope(project="foo", deliverable=None)


def test_detect_scope_in_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "deliverables" / "bar" / "design").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "deliverables" / "bar" / "design")
    assert detect_scope() == Scope(project="foo", deliverable="bar")


def test_detect_scope_in_project_subdir(monkeypatch, tmp_path) -> None:
    """Scope detection works from any subdir, not just design/."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "code").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "foo" / "code")
    assert detect_scope() == Scope(project="foo", deliverable=None)


def test_resolve_scope_or_fail_returns_existing_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "design").mkdir(parents=True)
    (tmp_path / "foo" / "design" / "project.toml").write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-28\n'
    )
    monkeypatch.chdir(tmp_path / "foo" / "design")
    from keel.workspace import resolve_scope_or_fail
    scope = resolve_scope_or_fail()
    assert scope.project == "foo"
    assert scope.deliverable is None


def test_resolve_scope_or_fail_rejects_missing_manifest(monkeypatch, tmp_path) -> None:
    """Path is structurally inside ~/projects/<X>/ but no project.toml there."""
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "ghost" / "design").mkdir(parents=True)  # no project.toml
    monkeypatch.chdir(tmp_path / "ghost" / "design")
    from keel.workspace import resolve_scope_or_fail
    import typer
    with pytest.raises(typer.Exit) as exc:
        resolve_scope_or_fail()
    assert exc.value.exit_code == 1


def test_deliverable_exists_true(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "deliverables" / "bar" / "design").mkdir(parents=True)
    (tmp_path / "foo" / "deliverables" / "bar" / "design" / "deliverable.toml").write_text(
        '[deliverable]\nname = "bar"\nparent_project = "foo"\ndescription = "d"\ncreated = 2026-04-28\nshared_worktree = false\n'
    )
    from keel.workspace import deliverable_exists
    assert deliverable_exists("foo", "bar") is True


def test_deliverable_exists_false(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import deliverable_exists
    assert deliverable_exists("foo", "bar") is False


def test_resolve_cli_scope_explicit_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "design").mkdir(parents=True)
    (tmp_path / "foo" / "design" / "project.toml").write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-28\n'
    )
    from keel.workspace import resolve_cli_scope
    scope = resolve_cli_scope(project="foo", deliverable=None)
    assert scope.project == "foo"
    assert scope.deliverable is None


def test_resolve_cli_scope_falls_back_to_cwd(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    (tmp_path / "foo" / "design").mkdir(parents=True)
    (tmp_path / "foo" / "design" / "project.toml").write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-28\n'
    )
    monkeypatch.chdir(tmp_path / "foo" / "design")
    from keel.workspace import resolve_cli_scope
    scope = resolve_cli_scope(project=None)
    assert scope.project == "foo"


def test_resolve_cli_scope_missing_project_exits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    from keel.workspace import resolve_cli_scope
    import typer
    with pytest.raises(typer.Exit) as exc:
        resolve_cli_scope(project=None)
    assert exc.value.exit_code == 1


def test_resolve_cli_scope_unknown_project_exits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import resolve_cli_scope
    import typer
    with pytest.raises(typer.Exit) as exc:
        resolve_cli_scope(project="ghost")
    assert exc.value.exit_code == 1


def test_decisions_dir_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import decisions_dir
    assert decisions_dir("foo") == tmp_path / "foo" / "design" / "decisions"


def test_decisions_dir_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    from keel.workspace import decisions_dir
    assert decisions_dir("foo", "bar") == tmp_path / "foo" / "deliverables" / "bar" / "design" / "decisions"


def test_resolve_scope_or_fail_returns_deliverable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path))
    proj = tmp_path / "foo" / "deliverables" / "bar" / "design"
    proj.mkdir(parents=True)
    (proj.parent.parent.parent / "design").mkdir(parents=True)
    (proj.parent.parent.parent / "design" / "project.toml").write_text(
        '[project]\nname = "foo"\ndescription = "d"\ncreated = 2026-04-28\n'
    )
    (proj / "deliverable.toml").write_text(
        '[deliverable]\nname = "bar"\nparent_project = "foo"\ndescription = "d"\ncreated = 2026-04-28\nshared_worktree = false\n'
    )
    monkeypatch.chdir(proj)
    from keel.workspace import resolve_scope_or_fail
    scope = resolve_scope_or_fail()
    assert scope.project == "foo"
    assert scope.deliverable == "bar"
