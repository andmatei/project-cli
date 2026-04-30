"""Tests for `keel task show`."""

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


def test_show_basic(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "show", "t2"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "t2" in result.stdout
    assert "t1" in result.stdout  # dep listed
    assert "Second" in result.stdout


def test_show_json(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    _seed(proj, monkeypatch)
    result = runner.invoke(app, ["task", "show", "t2", "--json"])
    data = json.loads(result.stdout)
    assert data["id"] == "t2"
    assert data["depends_on"] == ["t1"]
    assert "deps_status" in data
    assert data["deps_status"] == [{"id": "t1", "status": "planned"}]


def test_show_unknown(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["task", "show", "nothing"])
    assert result.exit_code == 1
