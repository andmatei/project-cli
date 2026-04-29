"""Tests for `keel migrate` (legacy Bash CLI projects → manifests)."""
from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def _write_legacy_project(projects, name: str, body: str) -> None:
    """Helper: scaffold a project in the old Bash CLI shape (no manifest)."""
    proj = projects / name
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text(body)
    (proj / "design" / "scope.md").write_text(f"# {name}\nScope.\n")
    (proj / "design" / "design.md").write_text(f"# {name}\nDesign.\n")
    (proj / "design" / ".phase").write_text("scoping\n")


def test_migrate_dry_run_default(projects) -> None:
    """Without --apply, migrate must not write anything."""
    _write_legacy_project(projects, "legacy", "# legacy\n\nold project.\n\n## Code\nCode: ../code/\nSource repo: /tmp/some-repo\n\n## Workflow\n")
    result = runner.invoke(app, ["migrate", "legacy"])
    assert result.exit_code == 0
    assert not (projects / "legacy" / "design" / "project.toml").exists()


def test_migrate_unknown_project(projects) -> None:
    result = runner.invoke(app, ["migrate", "ghost"])
    assert result.exit_code == 1


def test_migrate_skips_already_migrated(projects, make_project) -> None:
    """If project.toml already exists, migrate is a no-op (info, exit 0)."""
    make_project("foo")  # already has project.toml
    result = runner.invoke(app, ["migrate", "foo"])
    assert result.exit_code == 0
    assert "already" in result.stderr.lower() or "skipping" in result.stderr.lower()


def test_parse_code_section_single_repo() -> None:
    from keel.commands.migrate import _parse_code_section

    text = "## Code\nCode: ../code/\nSource repo: /tmp/some-repo\n"
    repos, shared = _parse_code_section(text, "myproj")
    assert shared is False
    assert len(repos) == 1
    assert repos[0].worktree == "code"
    assert repos[0].remote == "/tmp/some-repo"
    assert repos[0].local_hint == "/tmp/some-repo"


def test_parse_code_section_multi_repo() -> None:
    from keel.commands.migrate import _parse_code_section

    text = """## Code
Code (mms): ../code-mms/
Code (ipa): ../code-ipa/
Source repos: /Users/me/mms /Users/me/ipa
"""
    repos, shared = _parse_code_section(text, "myproj")
    assert shared is False
    assert len(repos) == 2
    worktrees = {r.worktree for r in repos}
    assert worktrees == {"code-mms", "code-ipa"}
    remotes = {r.remote for r in repos}
    assert remotes == {"/Users/me/mms", "/Users/me/ipa"}


def test_parse_code_section_shared() -> None:
    from keel.commands.migrate import _parse_code_section

    text = "## Code\nCode: shared with parent (../../../code/)\nSource repo: see parent\n"
    repos, shared = _parse_code_section(text, "myproj")
    assert shared is True
    assert repos == []


def test_parse_code_section_design_only() -> None:
    from keel.commands.migrate import _parse_code_section

    text = "## Workflow\n..."
    repos, shared = _parse_code_section(text, "myproj")
    assert shared is False
    assert repos == []


def test_enrich_repos_with_branch_from_worktree(projects, source_repo) -> None:
    """When a worktree exists, branch_prefix is filled from the current branch."""
    from keel import git_ops
    from keel.commands.migrate import _enrich_with_worktree_state
    from keel.manifest import RepoSpec

    # Stage a project dir with an existing worktree
    proj = projects / "legacy"
    proj.mkdir()
    git_ops.create_worktree(source_repo, proj / "code", branch="alice/legacy-base")

    repos = [RepoSpec(remote=str(source_repo), worktree="code")]
    enriched = _enrich_with_worktree_state(proj, repos)
    assert enriched[0].branch_prefix == "alice/legacy-base"
