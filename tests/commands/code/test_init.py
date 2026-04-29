# tests/commands/code/test_init.py
"""Tests for `keel code init`."""
from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_init_creates_missing_worktree(projects, make_project, source_repo) -> None:
    """If a manifest declares a worktree that doesn't exist, init creates it."""
    from datetime import date

    from keel.manifest import (
        ProjectManifest,
        ProjectMeta,
        RepoSpec,
        save_project_manifest,
    )
    proj = make_project("foo")
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[RepoSpec(
            remote=str(source_repo),
            local_hint=str(source_repo),
            worktree="code",
            branch_prefix="alice/foo",
        )],
    )
    save_project_manifest(proj / "design" / "project.toml", m)

    result = runner.invoke(app, ["code", "init", "--project", "foo", "-y"])
    assert result.exit_code == 0
    assert (proj / "code").is_dir()
    assert (proj / "code" / "README").is_file()


def test_init_idempotent(projects, make_project, source_repo) -> None:
    """init is idempotent — running twice doesn't error or create duplicate worktrees."""
    from datetime import date

    from keel.manifest import (
        ProjectManifest,
        ProjectMeta,
        RepoSpec,
        save_project_manifest,
    )
    proj = make_project("foo")
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[RepoSpec(
            remote=str(source_repo),
            local_hint=str(source_repo),
            worktree="code",
            branch_prefix="alice/foo",
        )],
    )
    save_project_manifest(proj / "design" / "project.toml", m)
    runner.invoke(app, ["code", "init", "--project", "foo", "-y"])
    result = runner.invoke(app, ["code", "init", "--project", "foo", "-y"])
    assert result.exit_code == 0


def test_init_dry_run_writes_nothing(projects, make_project, source_repo) -> None:
    from datetime import date

    from keel.manifest import (
        ProjectManifest,
        ProjectMeta,
        RepoSpec,
        save_project_manifest,
    )
    proj = make_project("foo")
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[RepoSpec(remote=str(source_repo), local_hint=str(source_repo), worktree="code", branch_prefix="a/f")],
    )
    save_project_manifest(proj / "design" / "project.toml", m)
    result = runner.invoke(app, ["code", "init", "--project", "foo", "--dry-run", "-y"])
    assert result.exit_code == 0
    assert not (proj / "code").exists()
    assert "[dry-run]" in result.stderr


def test_init_fails_when_local_repo_missing_without_clone_flag(projects, make_project) -> None:
    """If local_hint points to a missing dir and --clone-missing not set, fail."""
    from datetime import date

    from keel.manifest import (
        ProjectManifest,
        ProjectMeta,
        RepoSpec,
        save_project_manifest,
    )
    proj = make_project("foo")
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[RepoSpec(
            remote="git@e.com:o/r.git",
            local_hint=str(projects / "_does_not_exist"),
            worktree="code",
            branch_prefix="a/f",
        )],
    )
    save_project_manifest(proj / "design" / "project.toml", m)
    result = runner.invoke(app, ["code", "init", "--project", "foo", "-y"])
    assert result.exit_code == 1
    assert "missing" in result.stderr.lower() or "not found" in result.stderr.lower()
