"""Tests for `keel milestone start/done/cancel`."""

import pytest
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


@pytest.mark.parametrize(
    "setup_actions,expected_initial",
    [
        ([], "planned"),
        ([("milestone", "start", "m1")], "active"),
        ([("milestone", "start", "m1"), ("milestone", "done", "m1")], "done"),
    ],
    ids=["from_planned", "from_active", "from_done"],
)
def test_cancel_from_state(projects, make_project, monkeypatch, setup_actions, expected_initial) -> None:
    """Cancel works from any non-terminal state and from `done`."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "x"])
    for cmd in setup_actions:
        runner.invoke(app, list(cmd))
    m_state = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m_state.milestones[0].status == expected_initial
    result = runner.invoke(app, ["milestone", "cancel", "m1", "-y"])
    assert result.exit_code == 0
    m_after = load_milestones_manifest(proj / "design" / "milestones.toml")
    assert m_after.milestones[0].status == "cancelled"


def test_done_dry_run_writes_nothing(projects, make_project, monkeypatch) -> None:
    """Dry-run validates but does not mark milestone as done."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["milestone", "add", "m1", "--title", "Foundation"])
    runner.invoke(app, ["milestone", "start", "m1"])

    # Capture pre-state
    mp = proj / "design" / "milestones.toml"
    pre_text = mp.read_text()

    result = runner.invoke(app, ["milestone", "done", "m1", "--dry-run"], catch_exceptions=False)
    assert result.exit_code == 0
    # Confirm status unchanged
    post_text = mp.read_text()
    assert pre_text == post_text
    m = load_milestones_manifest(mp)
    assert m.milestones[0].status == "active"
