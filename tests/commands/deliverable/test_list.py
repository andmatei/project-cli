"""Tests for `keel deliverable list`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_list_empty(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["deliverable", "list", "--project", "foo"])
    assert result.exit_code == 0
    # Empty output or "(no deliverables)" — accept either.
    assert "no deliverables" in result.stdout.lower() or result.stdout.strip() == ""


def test_list_one_deliverable(projects, make_project, make_deliverable) -> None:
    make_deliverable(project_name="foo", name="bar", description="the bar")
    result = runner.invoke(app, ["deliverable", "list", "--project", "foo"])
    assert result.exit_code == 0
    assert "bar" in result.stdout


def test_list_json_shape(projects, make_project, make_deliverable) -> None:
    make_deliverable(project_name="foo", name="bar", description="the bar")
    result = runner.invoke(app, ["deliverable", "list", "--project", "foo", "--json"])
    payload = json.loads(result.stdout)
    assert "deliverables" in payload
    assert payload["deliverables"][0]["name"] == "bar"
    assert payload["deliverables"][0]["phase"] == "scoping"
    assert payload["deliverables"][0]["description"] == "the bar"


def test_list_auto_detects_project_from_cwd(
    projects, make_project, make_deliverable, monkeypatch
) -> None:
    proj = make_deliverable(project_name="foo", name="bar", description="d").parent.parent
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["deliverable", "list"])
    assert result.exit_code == 0
    assert "bar" in result.stdout
