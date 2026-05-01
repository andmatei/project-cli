"""Tests for `keel task next`."""

import json

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_milestones_manifest

runner = CliRunner()


def _seed(proj, monkeypatch):
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "M1"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "First"])
    runner.invoke(
        app, ["task", "add", "t2", "--milestone", "m1", "--title", "Second", "--depends-on", "t1"]
    )


def test_next_returns_topo_first_ready(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "next", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["id"] == "t1"


def test_next_no_ready_tasks_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["task", "next"])
    assert result.exit_code == 1


def test_next_with_milestone_filter(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "M1"])
    runner.invoke(app, ["milestone", "add", "m2", "--title", "M2"])
    runner.invoke(app, ["task", "add", "a", "--milestone", "m1", "--title", "x"])
    runner.invoke(app, ["task", "add", "b", "--milestone", "m2", "--title", "y"])
    result = runner.invoke(app, ["task", "next", "--milestone", "m2", "--json"])
    data = json.loads(result.stdout)
    assert data["id"] == "b"


def test_next_start_flag(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "next", "--start"])
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    t1 = next(t for t in m.tasks if t.id == "t1")
    assert t1.status == "active"
    assert t1.branch is not None
