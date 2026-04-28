"""Tests for `keel decision list`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_list_empty(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["decision", "list"])
    assert result.exit_code == 0


def test_list_one_decision(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["decision", "new", "Pick a thing", "--no-edit"])
    result = runner.invoke(app, ["decision", "list"])
    assert "Pick a thing" in result.stdout or "pick-a-thing" in result.stdout


def test_list_json(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["decision", "new", "Pick a thing", "--no-edit"])
    result = runner.invoke(app, ["decision", "list", "--json"])
    payload = json.loads(result.stdout)
    assert "decisions" in payload
    assert len(payload["decisions"]) == 1
    d = payload["decisions"][0]
    assert d["title"] == "Pick a thing"
    assert d["status"] == "proposed"
    assert d["slug"]
    assert d["date"]
