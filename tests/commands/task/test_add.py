"""Tests for `keel task add`."""

import json

import pytest
from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_milestones_manifest

runner = CliRunner()


def _setup_milestone(proj):
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])


def test_add_creates_first_task(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _setup_milestone(proj)
    result = runner.invoke(
        app, ["task", "add", "t1", "--milestone", "m1", "--title", "Set up"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert len(m.tasks) == 1
    assert m.tasks[0].id == "t1"
    assert m.tasks[0].milestone == "m1"
    assert m.tasks[0].status == "planned"
    assert m.tasks[0].depends_on == []


def test_add_with_dependencies(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _setup_milestone(proj)
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "First"])
    result = runner.invoke(
        app,
        [
            "task", "add", "t2", "--milestone", "m1", "--title", "Second",
            "--depends-on", "t1",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    t2 = next(t for t in m.tasks if t.id == "t2")
    assert t2.depends_on == ["t1"]


def test_add_with_multiple_dependencies(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _setup_milestone(proj)
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "a"])
    runner.invoke(app, ["task", "add", "t2", "--milestone", "m1", "--title", "b"])
    result = runner.invoke(
        app,
        [
            "task", "add", "t3", "--milestone", "m1", "--title", "c",
            "--depends-on", "t1,t2",
        ],
    )
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    t3 = next(t for t in m.tasks if t.id == "t3")
    assert sorted(t3.depends_on) == ["t1", "t2"]


def test_add_unknown_milestone_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app, ["task", "add", "t1", "--milestone", "ghost", "--title", "x"],
    )
    assert result.exit_code == 1
    assert "milestone" in result.stderr.lower()


def test_add_unknown_dependency_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _setup_milestone(proj)
    result = runner.invoke(
        app,
        [
            "task", "add", "t1", "--milestone", "m1", "--title", "x",
            "--depends-on", "nonexistent",
        ],
    )
    assert result.exit_code == 1


def test_add_rejects_cycle_in_existing_manifest(projects, make_project, monkeypatch) -> None:
    """Adding a task fails if the loaded manifest already contains a cycle (DAG validation runs on save)."""
    import tomlkit

    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "M1"])
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "a"])
    runner.invoke(
        app, ["task", "add", "t2", "--milestone", "m1", "--title", "b", "--depends-on", "t1"]
    )
    # Inject a cycle: t1 depends on t2
    mp = proj / "design" / "milestones.toml"
    doc = tomlkit.parse(mp.read_text())
    for t in doc["tasks"]:
        if t["id"] == "t1":
            t["depends_on"] = ["t2"]
    mp.write_text(tomlkit.dumps(doc))

    # Now adding any new task triggers validate_dag and exits 1
    result = runner.invoke(app, ["task", "add", "t3", "--milestone", "m1", "--title", "c"])
    assert result.exit_code == 1
    assert "cycle" in result.stderr.lower()


def test_add_duplicate_id_rejected(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _setup_milestone(proj)
    runner.invoke(app, ["task", "add", "t1", "--milestone", "m1", "--title", "First"])
    result = runner.invoke(
        app, ["task", "add", "t1", "--milestone", "m1", "--title", "Second"],
    )
    assert result.exit_code == 1


def test_add_json(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _setup_milestone(proj)
    result = runner.invoke(
        app,
        ["task", "add", "t1", "--milestone", "m1", "--title", "Set up", "--json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["id"] == "t1"
    assert data["milestone"] == "m1"
    assert data["status"] == "planned"
