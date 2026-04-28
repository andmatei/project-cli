"""Tests for `keel new`."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_project_manifest

runner = CliRunner()


def test_new_creates_design_dir(projects) -> None:
    result = runner.invoke(
        app,
        ["new", "foo", "-d", "A test project", "--no-worktree", "-y"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, (result.stdout, result.stderr)
    proj = projects / "foo"
    assert (proj / "design" / "CLAUDE.md").is_file()
    assert (proj / "design" / "scope.md").is_file()
    assert (proj / "design" / "design.md").is_file()
    assert (proj / "design" / ".phase").read_text().splitlines()[0] == "scoping"
    assert (proj / "design" / "project.toml").is_file()
    decisions = list((proj / "design" / "decisions").glob("*.md"))
    assert len(decisions) == 1
    assert "project-setup" in decisions[0].name


def test_new_writes_valid_manifest(projects) -> None:
    runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    m = load_project_manifest(projects / "foo" / "design" / "project.toml")
    assert m.project.name == "foo"
    assert m.project.description == "test"
    assert m.repos == []


def test_new_fails_if_project_exists(projects) -> None:
    runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    result = runner.invoke(app, ["new", "foo", "-d", "test", "--no-worktree", "-y"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr


def test_new_fails_without_description_non_tty(projects) -> None:
    """When stdin is not a tty, missing --description exits with code 2."""
    result = runner.invoke(app, ["new", "foo", "--no-worktree", "-y"], input="")
    assert result.exit_code == 2


def test_new_json_output(projects) -> None:
    result = runner.invoke(
        app,
        ["new", "foo", "-d", "t", "--no-worktree", "-y", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["path"].endswith("/foo")
    assert payload["worktrees"] == []
    # JSON mode suppresses info logs:
    assert "Created project" not in result.stderr


def test_new_with_one_repo_creates_worktree(projects, source_repo) -> None:
    result = runner.invoke(
        app,
        ["new", "foo", "-d", "t", "-r", str(source_repo), "-y"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    assert (projects / "foo" / "code").is_dir()
    assert (projects / "foo" / "code" / "README").is_file()


def test_new_with_one_repo_writes_repo_to_manifest(projects, source_repo) -> None:
    runner.invoke(app, ["new", "foo", "-d", "t", "-r", str(source_repo), "-y"])
    m = load_project_manifest(projects / "foo" / "design" / "project.toml")
    assert len(m.repos) == 1
    assert m.repos[0].worktree == "code"


def test_new_with_invalid_repo_exits_1(projects, tmp_path) -> None:
    not_a_repo = tmp_path / "nope"
    not_a_repo.mkdir()
    result = runner.invoke(app, ["new", "foo", "-d", "t", "-r", str(not_a_repo), "-y"])
    assert result.exit_code == 1
    assert "not a git repo" in result.stderr.lower()


def test_new_with_two_repos_creates_named_worktrees(projects, tmp_path) -> None:
    import subprocess

    repos = []
    for name in ("alpha", "beta"):
        r = tmp_path / f"src_{name}"
        r.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=r, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=r, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=r, check=True)
        (r / "README").write_text(name)
        subprocess.run(["git", "add", "."], cwd=r, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=r, check=True, capture_output=True)
        repos.append(str(r))
    result = runner.invoke(
        app,
        ["new", "multi", "-d", "two repos", "-r", repos[0], "-r", repos[1], "-y"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    assert (projects / "multi" / "code-src_alpha").is_dir()
    assert (projects / "multi" / "code-src_beta").is_dir()
    m = load_project_manifest(projects / "multi" / "design" / "project.toml")
    assert len(m.repos) == 2
    worktrees = {r.worktree for r in m.repos}
    assert worktrees == {"code-src_alpha", "code-src_beta"}


def test_new_dry_run_writes_nothing(projects, source_repo) -> None:
    result = runner.invoke(
        app,
        ["new", "foo", "-d", "t", "-r", str(source_repo), "--dry-run", "-y"],
    )
    assert result.exit_code == 0
    assert not (projects / "foo").exists()


def test_new_dry_run_lists_planned_ops(projects, source_repo) -> None:
    result = runner.invoke(
        app,
        ["new", "foo", "-d", "t", "-r", str(source_repo), "--dry-run", "-y"],
    )
    assert "[dry-run]" in result.stderr
    assert "project.toml" in result.stderr
    assert "scope.md" in result.stderr
    assert "design.md" in result.stderr
    assert "CLAUDE.md" in result.stderr
    assert "git worktree" in result.stderr.lower()
