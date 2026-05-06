"""Tests for `keel task move`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_move_reparents(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])  # creates default
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])

    result = runner.invoke(app, ["task", "move", "t1", "--milestone", "m1"])
    assert result.exit_code == 0
    from keel.api import load_milestones_manifest

    m = load_milestones_manifest(proj / "milestones.toml")
    t1 = next(t for t in m.tasks if t.id == "t1")
    assert t1.milestone == "m1"


def test_move_unknown_milestone_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])
    result = runner.invoke(app, ["task", "move", "t1", "--milestone", "ghost"])
    assert result.exit_code == 1


def test_move_unknown_task_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["milestone", "add", "m1", "--title", "x"])
    result = runner.invoke(app, ["task", "move", "ghost", "--milestone", "m1"])
    assert result.exit_code == 1


def test_move_emptying_default_removes_it(projects, make_project, monkeypatch) -> None:
    """When the last task leaves 'default', the auto-created milestone disappears."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["task", "add", "t1", "--title", "x"])  # creates default
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    runner.invoke(app, ["task", "move", "t1", "--milestone", "m1"])
    from keel.api import load_milestones_manifest

    m = load_milestones_manifest(proj / "milestones.toml")
    ids = {ms.id for ms in m.milestones}
    assert "default" not in ids
