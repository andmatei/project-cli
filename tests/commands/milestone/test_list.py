"""Tests for `keel milestone list`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_list_empty(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["milestone", "list"], catch_exceptions=False)
    assert result.exit_code == 0


def test_list_after_add(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    runner.invoke(app, ["milestone", "add", "m2", "--title", "Polish"])
    result = runner.invoke(app, ["milestone", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "m1" in result.stdout
    assert "m2" in result.stdout
    assert "Foundation" in result.stdout
    assert "Polish" in result.stdout


def test_list_json(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    result = runner.invoke(app, ["milestone", "list", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "milestones" in data
    assert len(data["milestones"]) == 1
    assert data["milestones"][0]["id"] == "m1"


def test_list_status_filter(projects, make_project, monkeypatch) -> None:
    """--status filter shows only milestones in that state."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "First"])
    runner.invoke(app, ["milestone", "add", "m2", "--title", "Second"])
    # Both default to planned. Filter by 'active' should yield none.
    result = runner.invoke(app, ["milestone", "list", "--status", "active", "--json"])
    data = json.loads(result.stdout)
    assert len(data["milestones"]) == 0

    result = runner.invoke(app, ["milestone", "list", "--status", "planned", "--json"])
    data = json.loads(result.stdout)
    assert len(data["milestones"]) == 2
