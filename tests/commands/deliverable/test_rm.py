"""Tests for `keel deliverable rm`."""
from typer.testing import CliRunner
from keel.app import app

runner = CliRunner()


def test_rm_removes_design_dir(projects, make_project, make_deliverable) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    result = runner.invoke(
        app,
        ["deliverable", "rm", "bar", "-y", "--project", "foo"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    assert not deliv.exists()


def test_rm_cleans_parent_claude_md(projects, make_project) -> None:
    """After deliverable rm, the parent's CLAUDE.md no longer mentions it."""
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    parent_claude = (projects / "foo" / "design" / "CLAUDE.md").read_text()
    assert "bar" in parent_claude  # Sanity: it's there before rm
    runner.invoke(app, ["deliverable", "rm", "bar", "-y", "--project", "foo"])
    parent_claude_after = (projects / "foo" / "design" / "CLAUDE.md").read_text()
    # The deliverable line is removed (not the heading itself necessarily):
    assert "**bar**" not in parent_claude_after


def test_rm_fails_for_unknown_deliverable(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["deliverable", "rm", "ghost", "-y", "--project", "foo"])
    assert result.exit_code == 1
    assert "ghost" in result.stderr.lower()


def test_rm_dry_run_writes_nothing(projects, make_project, make_deliverable) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    result = runner.invoke(app, ["deliverable", "rm", "bar", "-y", "--project", "foo", "--dry-run"])
    assert result.exit_code == 0
    assert deliv.exists()  # not actually removed
    assert "[dry-run]" in result.stderr


def test_rm_calls_remove_worktree_if_code_dir_present(projects, make_project, make_deliverable, monkeypatch) -> None:
    """If deliv/code exists, rm calls git_ops.remove_worktree on it."""
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    (deliv / "code").mkdir()
    calls = []
    def fake_remove(dest, *, force=False):
        calls.append((str(dest), force))
    monkeypatch.setattr("keel.git_ops.remove_worktree", fake_remove)
    runner.invoke(app, ["deliverable", "rm", "bar", "-y", "--project", "foo"])
    assert calls == [(str(deliv / "code"), False)]
