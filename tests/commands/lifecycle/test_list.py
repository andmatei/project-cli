"""Tests for `keel lifecycle list`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_list_includes_default(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    names = {lc["name"] for lc in data["lifecycles"]}
    assert "default" in names


def test_list_includes_user_library(projects) -> None:
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        """
name = "research"
description = "Research."
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
""".strip()
    )
    result = runner.invoke(app, ["lifecycle", "list", "--json"])
    data = json.loads(result.stdout)
    entry = next((lc for lc in data["lifecycles"] if lc["name"] == "research"), None)
    assert entry is not None
    assert entry["source"] == "user"
    assert entry["description"] == "Research."


def test_list_human_format(projects) -> None:
    result = runner.invoke(app, ["lifecycle", "list"])
    assert result.exit_code == 0
    assert "default" in result.stdout
