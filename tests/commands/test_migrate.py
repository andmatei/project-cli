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


def test_migrate_apply_writes_project_manifest(projects, source_repo) -> None:
    from keel import git_ops

    proj = projects / "legacy"
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text(
        f"# legacy\n\nold project.\n\n## Code\nCode: ../code/\nSource repo: {source_repo}\n\n## Workflow\n"
    )
    (proj / "design" / "scope.md").write_text("# legacy\n")
    (proj / "design" / "design.md").write_text("# legacy\n")
    (proj / "design" / ".phase").write_text("scoping\n")
    git_ops.create_worktree(source_repo, proj / "code", branch="alice/legacy-base")

    result = runner.invoke(app, ["migrate", "legacy", "--apply"])
    assert result.exit_code == 0, result.stderr
    from keel.manifest import load_project_manifest

    m = load_project_manifest(proj / "design" / "project.toml")
    assert m.project.name == "legacy"
    assert len(m.repos) == 1
    assert m.repos[0].worktree == "code"
    assert m.repos[0].remote == str(source_repo)
    assert m.repos[0].branch_prefix == "alice/legacy-base"


def test_migrate_apply_design_only_project(projects) -> None:
    """Project with no '## Code' section migrates to a manifest with no repos."""
    proj = projects / "designer"
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text("# designer\n\nDesign-only.\n\n## Workflow\n")
    (proj / "design" / "scope.md").write_text("# designer\n")
    (proj / "design" / "design.md").write_text("# designer\n")
    (proj / "design" / ".phase").write_text("scoping\n")
    result = runner.invoke(app, ["migrate", "designer", "--apply"])
    assert result.exit_code == 0
    from keel.manifest import load_project_manifest

    m = load_project_manifest(proj / "design" / "project.toml")
    assert m.repos == []


def test_migrate_writes_deliverable_manifests(projects) -> None:
    """Each deliverable on disk gets a deliverable.toml after migration."""
    proj = projects / "legacy"
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text("# legacy\n\nold.\n\n## Workflow\n")
    (proj / "design" / "scope.md").write_text("# x\n")
    (proj / "design" / "design.md").write_text("# x\n")
    (proj / "design" / ".phase").write_text("scoping\n")

    # Add a deliverable with a shared worktree
    deliv = proj / "deliverables" / "alpha"
    (deliv / "design" / "decisions").mkdir(parents=True)
    (deliv / "design" / "CLAUDE.md").write_text(
        "# alpha\n\nthe alpha thing.\n\nParent design: ../../../design/\n\n"
        "## Code\nCode: shared with parent (../../../code/)\nSource repo: see parent\n\n## Workflow\n"
    )
    (deliv / "design" / "design.md").write_text("# alpha\n")
    # Note: no .phase yet — migrate should create it

    result = runner.invoke(app, ["migrate", "legacy", "--apply"])
    assert result.exit_code == 0, result.stderr
    from keel.manifest import load_deliverable_manifest

    m = load_deliverable_manifest(deliv / "design" / "deliverable.toml")
    assert m.deliverable.name == "alpha"
    assert m.deliverable.parent_project == "legacy"
    assert m.deliverable.shared_worktree is True
    assert m.repos == []
    # .phase was created
    assert (deliv / "design" / ".phase").read_text().splitlines()[0] == "scoping"


def test_migrate_skips_already_migrated_deliverable(projects) -> None:
    """A deliverable that already has deliverable.toml is left alone."""
    from datetime import date as _date

    from keel.manifest import (
        DeliverableManifest,
        DeliverableMeta,
        save_deliverable_manifest,
    )

    proj = projects / "legacy"
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text("# legacy\n\nold.\n\n## Workflow\n")
    (proj / "design" / "scope.md").write_text("# x\n")
    (proj / "design" / "design.md").write_text("# x\n")
    (proj / "design" / ".phase").write_text("scoping\n")

    deliv = proj / "deliverables" / "alpha"
    (deliv / "design" / "decisions").mkdir(parents=True)
    save_deliverable_manifest(
        deliv / "design" / "deliverable.toml",
        DeliverableManifest(
            deliverable=DeliverableMeta(
                name="alpha",
                parent_project="legacy",
                description="kept",
                created=_date(2025, 1, 1),
                shared_worktree=False,
            ),
            repos=[],
        ),
    )
    (deliv / "design" / "CLAUDE.md").write_text("# alpha\n\nDIFFERENT description.\n\n## Workflow\n")

    runner.invoke(app, ["migrate", "legacy", "--apply"])

    # The pre-existing manifest is preserved (not overwritten)
    from keel.manifest import load_deliverable_manifest

    m = load_deliverable_manifest(deliv / "design" / "deliverable.toml")
    assert m.deliverable.description == "kept"


def test_migrate_all_full_round_trip(projects, source_repo) -> None:
    """Migrate a legacy project + 2 deliverables, then validate runs clean."""
    from keel import git_ops

    proj = projects / "legacy"
    (proj / "design" / "decisions").mkdir(parents=True)
    (proj / "design" / "CLAUDE.md").write_text(
        f"""# legacy

A migrated project.

## Code
Code: ../code/
Source repo: {source_repo}

## Deliverables
- **alpha**: ../deliverables/alpha/design/ -- alpha thing
- **beta**: ../deliverables/beta/design/ -- beta thing

## Workflow
"""
    )
    (proj / "design" / "scope.md").write_text("# legacy\nscope.\n")
    (proj / "design" / "design.md").write_text("# legacy\ndesign.\n")
    (proj / "design" / ".phase").write_text("scoping\n")
    git_ops.create_worktree(source_repo, proj / "code", branch="me/legacy-base")

    for d_name in ("alpha", "beta"):
        d = proj / "deliverables" / d_name
        (d / "design" / "decisions").mkdir(parents=True)
        (d / "design" / "CLAUDE.md").write_text(
            f"""# {d_name}

The {d_name} thing.

Parent design: ../../../design/

## Code
Code: shared with parent (../../../code/)
Source repo: see parent

## Workflow
"""
        )
        (d / "design" / "design.md").write_text(f"# {d_name}\n")

    # Migrate everything
    result = runner.invoke(app, ["migrate", "--all", "--apply"])
    assert result.exit_code == 0, result.stderr

    # Manifests exist
    from keel.manifest import load_deliverable_manifest, load_project_manifest

    pm = load_project_manifest(proj / "design" / "project.toml")
    assert pm.project.name == "legacy"
    assert pm.repos[0].branch_prefix == "me/legacy-base"
    am = load_deliverable_manifest(proj / "deliverables" / "alpha" / "design" / "deliverable.toml")
    assert am.deliverable.shared_worktree is True
    bm = load_deliverable_manifest(proj / "deliverables" / "beta" / "design" / "deliverable.toml")
    assert bm.deliverable.shared_worktree is True

    # Both deliverables now have .phase
    assert (proj / "deliverables" / "alpha" / "design" / ".phase").read_text().splitlines()[0] == "scoping"
    assert (proj / "deliverables" / "beta" / "design" / ".phase").read_text().splitlines()[0] == "scoping"

    # validate runs clean (no FAILs; the parent CLAUDE.md still mentions both deliverables)
    import json

    val = runner.invoke(app, ["validate", "legacy", "--json"])
    payload = json.loads(val.stdout)
    assert payload["summary"]["fail"] == 0
