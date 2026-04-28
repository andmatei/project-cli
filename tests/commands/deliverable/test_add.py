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


def test_add_inserts_into_parent_claude_md(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "the bar", "-y", "--project", "foo"])
    parent_claude = (projects / "foo" / "design" / "CLAUDE.md").read_text()
    assert "## Deliverables" in parent_claude
    assert "bar" in parent_claude
    assert "the bar" in parent_claude


def test_add_inserts_into_parent_design_md(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "the bar", "-y", "--project", "foo"])
    parent_design = (projects / "foo" / "design" / "design.md").read_text()
    assert "## Deliverables" in parent_design
    assert "bar" in parent_design


def test_add_is_idempotent_in_parent_files(projects, make_project) -> None:
    """Adding the same deliverable twice doesn't duplicate the parent line.

    (We can't add twice via the command — it'll fail with 'already exists' —
    but the AST helper's idempotency means hand-editing won't double-up either.
    Verify by checking the parent's deliverables list contains exactly one
    'bar' entry.)
    """
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    parent_claude = (projects / "foo" / "design" / "CLAUDE.md").read_text()
    # Count occurrences of the deliverable bullet line:
    assert parent_claude.count("**bar**") == 1


def test_add_updates_sibling_deliverable_claude_md(projects, make_project) -> None:
    """Adding a second deliverable updates the first's CLAUDE.md sibling section."""
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "alpha", "-d", "alpha thing", "-y", "--project", "foo"])
    runner.invoke(app, ["deliverable", "add", "beta", "-d", "beta thing", "-y", "--project", "foo"])
    sibling_claude = (projects / "foo" / "deliverables" / "alpha" / "design" / "CLAUDE.md").read_text()
    # alpha's CLAUDE.md should mention beta:
    assert "beta" in sibling_claude


def test_add_with_repo_creates_worktree(projects, make_project, source_repo) -> None:
    make_project("foo")
    result = runner.invoke(
        app,
        ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo", "-r", str(source_repo)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    deliv = projects / "foo" / "deliverables" / "bar"
    assert (deliv / "code").is_dir()
    assert (deliv / "code" / "README").is_file()


def test_add_with_repo_writes_repo_to_manifest(projects, make_project, source_repo) -> None:
    make_project("foo")
    runner.invoke(
        app,
        ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo", "-r", str(source_repo)],
    )
    from keel.manifest import load_deliverable_manifest
    m = load_deliverable_manifest(projects / "foo" / "deliverables" / "bar" / "design" / "deliverable.toml")
    assert len(m.repos) == 1
    assert m.repos[0].worktree == "code"


def test_add_shared_marks_manifest_and_no_repos(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo", "--shared"])
    from keel.manifest import load_deliverable_manifest
    m = load_deliverable_manifest(projects / "foo" / "deliverables" / "bar" / "design" / "deliverable.toml")
    assert m.deliverable.shared_worktree is True
    assert m.repos == []


def test_add_lists_existing_siblings_in_new_deliverable_claude(projects, make_project) -> None:
    """When adding B after A exists, B's own CLAUDE.md should list A as a sibling."""
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "alpha", "-d", "alpha thing", "-y", "--project", "foo"])
    runner.invoke(app, ["deliverable", "add", "beta", "-d", "beta thing", "-y", "--project", "foo"])
    beta_claude = (projects / "foo" / "deliverables" / "beta" / "design" / "CLAUDE.md").read_text()
    # Both directions of sibling reference should be present:
    assert "alpha" in beta_claude
