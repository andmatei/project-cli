"""Tests for keel plugin doctor command."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_doctor_clean_project(projects, make_project, monkeypatch) -> None:
    """Test plugin doctor on a clean project."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["plugin", "doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["findings"] == []


def test_doctor_flags_unknown_provider(projects, make_project, monkeypatch) -> None:
    """Test plugin doctor flags unknown ticketing provider."""
    from keel.api import load_project_manifest, save_project_manifest

    proj = make_project("foo")
    pm = load_project_manifest(proj / "design" / "project.toml")
    pm.extensions["ticketing"] = {"provider": "ghost"}
    save_project_manifest(proj / "design" / "project.toml", pm)
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["plugin", "doctor", "--json"])
    assert result.exit_code != 0
    data = json.loads(result.stdout)
    assert any("ghost" in f["message"] for f in data["findings"])
