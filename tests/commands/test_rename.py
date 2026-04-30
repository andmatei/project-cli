"""Tests for project-level `keel rename`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_rename_moves_project_dir(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["rename", "foo", "bar", "-y"])
    assert result.exit_code == 0
    assert not (projects / "foo").exists()
    assert (projects / "bar" / "design" / "project.toml").is_file()


def test_rename_updates_manifest_name(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["rename", "foo", "bar", "-y"])
    from keel.manifest import load_project_manifest

    m = load_project_manifest(projects / "bar" / "design" / "project.toml")
    assert m.project.name == "bar"


def test_rename_target_exists(projects, make_project) -> None:
    make_project("foo")
    make_project("bar")
    result = runner.invoke(app, ["rename", "foo", "bar", "-y"])
    assert result.exit_code == 1


def test_rename_with_worktree_uses_git_worktree_move(
    projects, make_project, source_repo, monkeypatch
) -> None:
    from datetime import date

    from keel import git_ops
    from keel.manifest import (
        ProjectManifest,
        ProjectMeta,
        RepoSpec,
        save_project_manifest,
    )

    proj = make_project("foo")
    git_ops.create_worktree(source_repo, proj / "code", branch="alice/foo")
    # Update manifest to declare the repo
    m = ProjectManifest(
        project=ProjectMeta(name="foo", description="d", created=date(2026, 4, 29)),
        repos=[
            RepoSpec(
                remote=str(source_repo),
                local_hint=str(source_repo),
                worktree="code",
                branch_prefix="alice/foo",
            )
        ],
    )
    save_project_manifest(proj / "design" / "project.toml", m)

    move_calls = []
    real_move = git_ops.move_worktree

    def spy(old, new):
        move_calls.append((str(old), str(new)))
        real_move(old, new)

    monkeypatch.setattr("keel.git_ops.move_worktree", spy)
    result = runner.invoke(app, ["rename", "foo", "bar", "-y"], catch_exceptions=False)
    assert result.exit_code == 0
    assert len(move_calls) == 1
    assert (projects / "bar" / "code" / "README").is_file()
