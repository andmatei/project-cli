"""Tests for `keel restore`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_restore_basic(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj.parent)
    runner.invoke(app, ["archive", "foo", "-y"])
    assert not proj.exists()
    # Archive creates foo-YYYY-MM-DD
    archived_dirs = list((projects / ".archive").glob("foo-*"))
    assert len(archived_dirs) == 1

    result = runner.invoke(app, ["restore", "foo", "-y"])
    assert result.exit_code == 0
    assert proj.is_dir()
    # The archived directory should be gone
    archived_dirs = list((projects / ".archive").glob("foo-*"))
    assert len(archived_dirs) == 0


def test_restore_unknown_fails(projects, monkeypatch) -> None:
    monkeypatch.chdir(projects)
    result = runner.invoke(app, ["restore", "nonexistent", "-y"])
    assert result.exit_code == 1


def test_restore_with_existing_target_fails(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj.parent)
    runner.invoke(app, ["archive", "foo", "-y"])
    # Now create a NEW foo project that conflicts
    make_project("foo")
    result = runner.invoke(app, ["restore", "foo", "-y"])
    assert result.exit_code == 1


def test_restore_dry_run(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj.parent)
    runner.invoke(app, ["archive", "foo", "-y"])
    archived_dirs = list((projects / ".archive").glob("foo-*"))
    assert len(archived_dirs) == 1
    result = runner.invoke(app, ["restore", "foo", "-y", "--dry-run"])
    assert result.exit_code == 0
    # Still archived after dry run
    archived_dirs = list((projects / ".archive").glob("foo-*"))
    assert len(archived_dirs) == 1
