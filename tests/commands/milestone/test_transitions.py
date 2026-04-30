"""Tests for `keel milestone start/done/cancel`."""

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_milestones_manifest

runner = CliRunner()


def _add(proj_dir):
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])


def test_start_planned_to_active(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    result = runner.invoke(app, ["milestone", "start", "m1"], catch_exceptions=False)
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m.milestones[0].status == "active"


def test_start_rejects_wrong_state(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    runner.invoke(app, ["milestone", "start", "m1"])  # planned -> active
    result = runner.invoke(app, ["milestone", "start", "m1"])  # already active
    assert result.exit_code == 1


def test_start_reopen_done_to_active(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    runner.invoke(app, ["milestone", "start", "m1"])
    runner.invoke(app, ["milestone", "done", "m1"])
    # Without --reopen, start fails
    result = runner.invoke(app, ["milestone", "start", "m1"])
    assert result.exit_code == 1
    # With --reopen, start succeeds
    result = runner.invoke(app, ["milestone", "start", "m1", "--reopen"])
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m.milestones[0].status == "active"


def test_done_active_to_done(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    runner.invoke(app, ["milestone", "start", "m1"])
    result = runner.invoke(app, ["milestone", "done", "m1"], catch_exceptions=False)
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m.milestones[0].status == "done"


def test_done_rejects_wrong_state(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    # Still planned, not active
    result = runner.invoke(app, ["milestone", "done", "m1"])
    assert result.exit_code == 1


def test_done_with_fan_out_blocks_when_subs_not_done(
    projects, make_project, make_deliverable, monkeypatch
) -> None:
    """Done on a fan-out milestone should fail if any sub-milestone isn't done."""
    proj = make_project("foo")
    make_deliverable(project_name="foo", name="alpha", description="d")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Big", "--project", "foo"])
    # Set fan_out manually via TOML edit
    import tomlkit
    mp = proj / "design" / "milestones.toml"
    doc = tomlkit.parse(mp.read_text())
    doc["milestones"][0]["fan_out"] = ["alpha"]
    mp.write_text(tomlkit.dumps(doc))

    runner.invoke(app, ["milestone", "start", "m1", "--project", "foo"])
    # No alpha sub-milestone yet → done should fail without --force
    result = runner.invoke(app, ["milestone", "done", "m1", "--project", "foo"])
    assert result.exit_code == 1

    # With --force, succeeds
    result = runner.invoke(app, ["milestone", "done", "m1", "--project", "foo", "--force"])
    assert result.exit_code == 0


def test_cancel_from_any_state(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    result = runner.invoke(app, ["milestone", "cancel", "m1", "-y"], catch_exceptions=False)
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m.milestones[0].status == "cancelled"


def test_cancel_active_milestone(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    _add(proj)
    runner.invoke(app, ["milestone", "start", "m1"])
    result = runner.invoke(app, ["milestone", "cancel", "m1", "-y"])
    assert result.exit_code == 0
    m = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m.milestones[0].status == "cancelled"
