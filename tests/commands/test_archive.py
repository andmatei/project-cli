"""Tests for `keel archive`."""
from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_archive_moves_project_to_archive(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["archive", "foo", "-y"])
    assert result.exit_code == 0
    assert not (projects / "foo").exists()
    archive_dirs = list((projects / ".archive").glob("foo-*"))
    assert len(archive_dirs) == 1
    assert (archive_dirs[0] / ".archived").is_file()
    assert (archive_dirs[0] / "design" / "project.toml").is_file()


def test_archive_unknown(projects) -> None:
    result = runner.invoke(app, ["archive", "ghost", "-y"])
    assert result.exit_code == 1


def test_archive_dry_run(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["archive", "foo", "-y", "--dry-run"])
    assert result.exit_code == 0
    assert (projects / "foo").exists()
    assert not (projects / ".archive").exists()


def test_archive_with_worktree_clean(projects, make_project, source_repo) -> None:
    """Archive correctly removes a clean worktree before moving the project."""
    from keel import git_ops
    proj = make_project("foo")
    git_ops.create_worktree(source_repo, proj / "code", branch="alice/foo")
    result = runner.invoke(app, ["archive", "foo", "-y"])
    assert result.exit_code == 0
    archive_dirs = list((projects / ".archive").glob("foo-*"))
    assert len(archive_dirs) == 1
    # Worktree was removed before move (so it's not in the archive):
    assert not (archive_dirs[0] / "code").exists()
