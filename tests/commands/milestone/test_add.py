"""Tests for `keel milestone add`."""

import json

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_milestones_manifest

runner = CliRunner()


def test_add_creates_first_milestone(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app, ["milestone", "add", "m1", "--title", "Foundation"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.stderr
    manifest_path = proj / "design" / "milestones.toml"
    assert manifest_path.is_file()
    m = load_milestones_manifest(manifest_path)
    assert len(m.milestones) == 1
    assert m.milestones[0].id == "m1"
    assert m.milestones[0].title == "Foundation"
    assert m.milestones[0].status == "planned"


def test_add_at_deliverable_level(projects, make_deliverable, monkeypatch) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    monkeypatch.chdir(deliv / "design")
    result = runner.invoke(
        app, ["milestone", "add", "m1", "--title", "Bar foundation"], catch_exceptions=False
    )
    assert result.exit_code == 0
    m = load_milestones_manifest(deliv / "design" / "milestones.toml")
    assert m.milestones[0].id == "m1"


def test_add_rejects_duplicate_id(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "First"])
    result = runner.invoke(
        app, ["milestone", "add", "m1", "--title", "Second"], catch_exceptions=False
    )
    assert result.exit_code == 1
    assert "exists" in result.stderr.lower() or "duplicate" in result.stderr.lower()


def test_add_json(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app, ["milestone", "add", "m1", "--title", "Foundation", "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["id"] == "m1"
    assert data["status"] == "planned"


def test_add_dry_run_writes_nothing(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app, ["milestone", "add", "m1", "--title", "Foundation", "--dry-run"]
    )
    assert result.exit_code == 0
    manifest_path = proj / "design" / "milestones.toml"
    assert not manifest_path.exists()


def test_add_no_push_flag_accepted(projects, make_project, monkeypatch) -> None:
    """--no-push is accepted even when no ticketing config exists; no-op for now."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app, ["milestone", "add", "m1", "--title", "Foundation", "--no-push"]
    )
    assert result.exit_code == 0
