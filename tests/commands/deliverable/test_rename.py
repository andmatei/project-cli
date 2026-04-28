"""Tests for `keel deliverable rename`."""
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_rename_moves_design_dir(projects, make_project, make_deliverable) -> None:
    old = make_deliverable(project_name="foo", name="bar", description="d")
    result = runner.invoke(
        app,
        ["deliverable", "rename", "bar", "baz", "-y", "--project", "foo"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    assert not old.exists()
    new = projects / "foo" / "deliverables" / "baz"
    assert new.is_dir()
    assert (new / "design" / "deliverable.toml").is_file()


def test_rename_updates_manifest_name(projects, make_project, make_deliverable) -> None:
    make_deliverable(project_name="foo", name="bar", description="d")
    runner.invoke(app, ["deliverable", "rename", "bar", "baz", "-y", "--project", "foo"])
    from keel.manifest import load_deliverable_manifest
    m = load_deliverable_manifest(projects / "foo" / "deliverables" / "baz" / "design" / "deliverable.toml")
    assert m.deliverable.name == "baz"


def test_rename_fails_if_target_exists(projects, make_project, make_deliverable) -> None:
    make_deliverable(project_name="foo", name="bar", description="d")
    make_deliverable(project_name="foo", name="baz", description="d")
    result = runner.invoke(app, ["deliverable", "rename", "bar", "baz", "-y", "--project", "foo"])
    assert result.exit_code == 1
    assert "exists" in result.stderr.lower()


def test_rename_updates_parent_references(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    runner.invoke(app, ["deliverable", "rename", "bar", "baz", "-y", "--project", "foo"])
    parent_claude = (projects / "foo" / "design" / "CLAUDE.md").read_text()
    assert "**bar**" not in parent_claude
    assert "**baz**" in parent_claude
