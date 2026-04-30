"""Tests for `keel task list`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def _setup(proj_dir, monkeypatch):
    monkeypatch.chdir(proj_dir / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "M1"])
    runner.invoke(app, ["milestone", "add", "m2", "--title", "M2"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "a"])
    runner.invoke(app, ["task", "add", "t2", "--milestone", "m1", "--title", "b", "--depends-on", "t1"])
    runner.invoke(app, ["task", "add", "t3", "--milestone", "m2", "--title", "c"])


def test_list_empty(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["task", "list"], catch_exceptions=False)
    assert result.exit_code == 0


def test_list_after_add(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _setup(proj, monkeypatch)
    result = runner.invoke(app, ["task", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "t1" in result.stdout
    assert "t2" in result.stdout
    assert "t3" in result.stdout


def test_list_filter_by_milestone(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _setup(proj, monkeypatch)
    result = runner.invoke(app, ["task", "list", "--milestone", "m1", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = {t["id"] for t in data["tasks"]}
    assert ids == {"t1", "t2"}


def test_list_filter_by_status(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _setup(proj, monkeypatch)
    result = runner.invoke(app, ["task", "list", "--status", "planned", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data["tasks"]) == 3


def test_list_ready(projects, make_project, monkeypatch) -> None:
    """--ready shows only tasks whose dependencies are all done."""
    proj = make_project("foo")
    _setup(proj, monkeypatch)
    # All tasks are planned, deps not yet done. Ready = tasks with no unmet deps = t1, t3.
    result = runner.invoke(app, ["task", "list", "--ready", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = {t["id"] for t in data["tasks"]}
    assert ids == {"t1", "t3"}


def test_list_blocked(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _setup(proj, monkeypatch)
    result = runner.invoke(app, ["task", "list", "--blocked", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = {t["id"] for t in data["tasks"]}
    assert ids == {"t2"}


def test_list_ready_and_blocked_mutually_exclusive(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["task", "list", "--ready", "--blocked"])
    assert result.exit_code != 0


def test_list_json_includes_ready_field(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _setup(proj, monkeypatch)
    result = runner.invoke(app, ["task", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    by_id = {t["id"]: t for t in data["tasks"]}
    assert by_id["t1"]["ready"] is True
    assert by_id["t2"]["ready"] is False  # depends on t1 (planned, not done)
    assert by_id["t3"]["ready"] is True
