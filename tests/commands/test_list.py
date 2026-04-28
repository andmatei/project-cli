"""Tests for `project-cli list`."""
import json

from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_list_empty(projects) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    # Empty workspace prints either nothing or a header but no project lines.
    assert "(no projects)" in result.stdout or result.stdout.strip() == ""


def test_list_one_project(projects, make_project) -> None:
    make_project("foo", "first project")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "foo" in result.stdout


def test_list_shows_phase(projects, make_project) -> None:
    make_project("foo", "first project")
    result = runner.invoke(app, ["list"])
    assert "scoping" in result.stdout


def test_list_json_empty_returns_empty_list(projects) -> None:
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"projects": []}


def test_list_json_shape(projects, make_project) -> None:
    make_project("foo", "first project")
    make_project("bar", "second project")
    result = runner.invoke(app, ["list", "--json"])
    payload = json.loads(result.stdout)
    assert "projects" in payload
    names = {p["name"] for p in payload["projects"]}
    assert names == {"foo", "bar"}
    for p in payload["projects"]:
        assert {"name", "phase", "description", "deliverable_count"} <= p.keys()


def test_list_phase_filter(projects, make_project) -> None:
    make_project("foo", "scoping project")
    bar = make_project("bar", "implementing project")
    (bar / "design" / ".phase").write_text("implementing\n")

    result = runner.invoke(app, ["list", "--phase", "implementing"])
    assert result.exit_code == 0
    assert "bar" in result.stdout
    assert "foo" not in result.stdout


def test_list_phase_filter_no_match(projects, make_project) -> None:
    """When --phase filter matches nothing but projects exist, message reflects that."""
    make_project("foo", "scoping project")
    result = runner.invoke(app, ["list", "--phase", "done"])
    assert result.exit_code == 0
    assert "no projects in phase 'done'" in result.stdout
