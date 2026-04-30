"""Tests for `keel task graph`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def _seed(proj, monkeypatch):
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "M1"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "First"])
    runner.invoke(
        app,
        ["task", "add", "t2", "--milestone", "m1", "--title", "Second", "--depends-on", "t1"],
    )
    runner.invoke(
        app,
        ["task", "add", "t3", "--milestone", "m1", "--title", "Third", "--depends-on", "t1"],
    )
    runner.invoke(
        app,
        [
            "task",
            "add",
            "t4",
            "--milestone",
            "m1",
            "--title",
            "Fourth",
            "--depends-on",
            "t2,t3",
        ],
    )


def test_graph_ascii(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "graph"], catch_exceptions=False)
    assert result.exit_code == 0
    for tid in ("t1", "t2", "t3", "t4"):
        assert tid in result.stdout


def test_graph_dot(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "graph", "--dot"], catch_exceptions=False)
    assert result.exit_code == 0
    body = result.stdout
    assert "digraph" in body
    assert "t1" in body
    assert "t2" in body
    # Edge syntax: source -> target
    assert "->" in body
    assert "}" in body


def test_graph_json(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "graph", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "tasks" in data
    ids = [t["id"] for t in data["tasks"]]
    # topological order: t1 first; t4 last
    assert ids[0] == "t1"
    assert ids[-1] == "t4"
    by_id = {t["id"]: t for t in data["tasks"]}
    assert by_id["t1"]["ready"] is True
    assert by_id["t2"]["blocked"] is True


def test_graph_milestone_filter(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "M1"])
    runner.invoke(app, ["milestone", "add", "m2", "--title", "M2"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "x"])
    runner.invoke(app, ["task", "add", "t2", "--milestone", "m2", "--title", "y"])
    result = runner.invoke(app, ["task", "graph", "--milestone", "m1", "--json"])
    data = json.loads(result.stdout)
    ids = {t["id"] for t in data["tasks"]}
    assert ids == {"t1"}


def test_graph_dot_and_json_mutually_exclusive(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["task", "graph", "--dot", "--json"])
    assert result.exit_code != 0
