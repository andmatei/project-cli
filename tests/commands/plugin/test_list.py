"""Tests for keel plugin list command."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_plugin_list_json() -> None:
    """Test plugin list with --json output."""
    result = runner.invoke(app, ["plugin", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "plugins" in data
    assert isinstance(data["plugins"], list)


def test_plugin_list_human_format() -> None:
    """Test plugin list with human-readable output."""
    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
