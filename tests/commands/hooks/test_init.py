"""Tests for `keel hooks init`."""

from __future__ import annotations

from typer.testing import CliRunner

from keel.app import app


def test_hooks_init_creates_workspace_dir(projects, monkeypatch) -> None:
    """`keel hooks init` with no flags scaffolds the workspace hooks dir."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "init"])
    assert result.exit_code == 0, result.stderr
    workspace_hooks = projects / ".keel" / "hooks"
    assert workspace_hooks.is_dir()
    assert (workspace_hooks / "README.md").is_file()


def test_hooks_init_project_mode(projects, make_project, monkeypatch) -> None:
    """`keel hooks init --project foo` scaffolds `<projects>/foo/.keel/hooks/`."""
    runner = CliRunner()
    proj = make_project("foo")
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["hooks", "init", "--project", "foo"])
    assert result.exit_code == 0, result.stderr
    assert (proj / ".keel" / "hooks").is_dir()
    assert (proj / ".keel" / "hooks" / "README.md").is_file()


def test_hooks_init_idempotent(projects, monkeypatch) -> None:
    """Re-running on an existing hooks dir is a no-op."""
    runner = CliRunner()
    monkeypatch.chdir(projects)
    first = runner.invoke(app, ["hooks", "init"])
    second = runner.invoke(app, ["hooks", "init"])
    assert first.exit_code == 0
    assert second.exit_code == 0
