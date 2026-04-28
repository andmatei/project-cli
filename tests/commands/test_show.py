"""Tests for `project-cli show`."""
import json
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_show_by_name(projects, make_project) -> None:
    make_project("foo", "the foo project")
    result = runner.invoke(app, ["show", "foo"])
    assert result.exit_code == 0, result.stderr
    assert "foo" in result.stdout
    assert "the foo project" in result.stdout
    assert "scoping" in result.stdout


def test_show_unknown_project(projects) -> None:
    result = runner.invoke(app, ["show", "doesnotexist"])
    assert result.exit_code == 1
    assert "not found" in result.stderr.lower()


def test_show_auto_detects_project_from_cwd(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo", "auto-detected")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0, result.stderr
    assert "foo" in result.stdout


def test_show_json_shape(projects, make_project) -> None:
    make_project("foo", "the foo project")
    result = runner.invoke(app, ["show", "foo", "--json"])
    payload = json.loads(result.stdout)
    assert payload["name"] == "foo"
    assert payload["description"] == "the foo project"
    assert payload["phase"] == "scoping"
    assert payload["repos"] == []
    assert payload["decision_count"] == 0
    assert payload["deliverables"] == []
