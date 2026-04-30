"""Tests for `keel milestone rm`."""

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_milestones_manifest

runner = CliRunner()


def test_rm_cancelled_milestone(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "T"])
    runner.invoke(app, ["milestone", "cancel", "m1", "-y"])
    result = runner.invoke(app, ["milestone", "rm", "m1", "-y"], catch_exceptions=False)
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m.milestones == []


def test_rm_active_milestone_blocked_without_force(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "T"])
    runner.invoke(app, ["milestone", "start", "m1"])
    result = runner.invoke(app, ["milestone", "rm", "m1", "-y"])
    assert result.exit_code == 1


def test_rm_with_force(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "T"])
    runner.invoke(app, ["milestone", "start", "m1"])
    result = runner.invoke(app, ["milestone", "rm", "m1", "-y", "--force"])
    assert result.exit_code == 0


def test_rm_unknown_id(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["milestone", "rm", "nonexistent", "-y"])
    assert result.exit_code == 1
