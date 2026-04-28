"""Tests for `keel deliverable add`."""
from typer.testing import CliRunner
from keel.app import app
from keel.manifest import load_deliverable_manifest

runner = CliRunner()


def test_add_creates_deliverable_design_dir(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(
        app,
        ["deliverable", "add", "bar", "-d", "the bar deliverable", "-y", "--project", "foo"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    deliv = projects / "foo" / "deliverables" / "bar"
    assert (deliv / "design" / "deliverable.toml").is_file()
    assert (deliv / "design" / "design.md").is_file()
    assert (deliv / "design" / "CLAUDE.md").is_file()
    assert (deliv / "design" / ".phase").read_text().splitlines()[0] == "scoping"
    # No scope.md by default (opt-in):
    assert not (deliv / "design" / "scope.md").exists()


def test_add_writes_valid_manifest(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    m = load_deliverable_manifest(projects / "foo" / "deliverables" / "bar" / "design" / "deliverable.toml")
    assert m.deliverable.name == "bar"
    assert m.deliverable.parent_project == "foo"
    assert m.deliverable.shared_worktree is False
    assert m.repos == []


def test_add_fails_if_deliverable_exists(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    result = runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr.lower()


def test_add_fails_if_parent_project_missing(projects) -> None:
    result = runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "ghost"])
    assert result.exit_code == 1
    assert "ghost" in result.stderr.lower()
