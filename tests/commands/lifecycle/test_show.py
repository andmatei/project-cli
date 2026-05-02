"""Tests for `keel lifecycle show`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_show_default(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "show", "default", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["name"] == "default"
    assert data["initial"] == "scoping"
    assert "scoping" in data["states"]


def test_show_human_includes_transitions(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "show", "default"])
    assert result.exit_code == 0
    assert "scoping" in result.stdout
    assert "designing" in result.stdout


def test_show_unknown_fails(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "show", "ghost"])
    assert result.exit_code != 0
    assert "ghost" in result.stderr.lower() or "lifecycle" in result.stderr.lower()
