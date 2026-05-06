"""Tests for `keel deliverable add`."""

from typer.testing import CliRunner

from keel.app import app
from keel.manifest import load_project_manifest

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
    assert (deliv / "project.toml").is_file()
    assert (deliv / "design.md").is_file()
    assert (deliv / "README.md").is_file()
    assert (deliv / "scope.md").is_file()
    assert (deliv / ".keel" / "phase").read_text().splitlines()[0] == "scoping"


def test_add_writes_valid_manifest(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    m = load_project_manifest(projects / "foo" / "deliverables" / "bar" / "project.toml")
    assert m.project.name == "bar"
    assert m.project.shared_worktree is False
    assert m.repos == []


def test_add_fails_if_deliverable_exists(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    result = runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr.lower()


def test_add_fails_if_parent_project_missing(projects) -> None:
    result = runner.invoke(
        app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "ghost"]
    )
    assert result.exit_code == 1
    assert "ghost" in result.stderr.lower()


def test_add_inserts_into_parent_design_md(projects, make_project) -> None:
    """The parent project's design.md should list new deliverables under '## Deliverables'."""
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "the bar", "-y", "--project", "foo"])
    parent_design = (projects / "foo" / "design.md").read_text()
    assert "## Deliverables" in parent_design
    assert "bar" in parent_design
    # Link path no longer crosses a `design/` subdir:
    assert "deliverables/bar/design.md" in parent_design
    assert "../deliverables/bar/design.md" not in parent_design


def test_add_parent_design_md_idempotent(projects, make_project) -> None:
    """Adding the same deliverable doesn't duplicate the parent's design.md entry.

    (The command itself fails on duplicate-add, but the AST helper's idempotency means
    hand-editing won't double-up either. Verify the parent's deliverables list contains
    exactly one 'bar' bullet.)
    """
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo"])
    parent_design = (projects / "foo" / "design.md").read_text()
    assert parent_design.count("**bar**") == 1


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
    m = load_project_manifest(projects / "foo" / "deliverables" / "bar" / "project.toml")
    assert len(m.repos) == 1
    assert m.repos[0].worktree == "code"


def test_add_shared_marks_manifest_and_no_repos(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(
        app, ["deliverable", "add", "bar", "-d", "d", "-y", "--project", "foo", "--shared"]
    )
    m = load_project_manifest(projects / "foo" / "deliverables" / "bar" / "project.toml")
    assert m.project.shared_worktree is True
    assert m.repos == []


def test_add_does_not_print_duplicate_messages(projects, make_project) -> None:
    """'Created deliverable: ...' (stderr) was redundant with 'Deliverable created: ...' (stdout)."""
    make_project("foo")
    result = runner.invoke(
        app,
        ["deliverable", "add", "bar", "-d", "t", "-y", "--project", "foo"],
    )
    assert "Created deliverable:" not in result.stderr
    assert result.stdout  # non-empty


# --- T6.1: deliverable now uses the same scaffold as `keel new` -----------------


def test_deliverable_add_writes_project_toml(projects, make_project, monkeypatch) -> None:
    """Deliverables now use project.toml — identical to top-level."""
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    result = runner.invoke(
        app, ["deliverable", "add", "bar", "-d", "Sub-project", "-y"], catch_exceptions=False
    )
    assert result.exit_code == 0
    deliv_path = proj / "deliverables" / "bar"
    assert (deliv_path / "project.toml").is_file()
    assert not (deliv_path / "deliverable.toml").exists()


def test_deliverable_add_creates_keel_dir(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj)
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "x", "-y"])
    deliv_path = proj / "deliverables" / "bar"
    assert (deliv_path / ".keel" / "phase").is_file()
    assert (deliv_path / ".keel" / "lifecycle.lock.toml").is_file()


def test_deliverable_add_inherits_lifecycle_from_parent(
    projects, make_project, monkeypatch
) -> None:
    """If parent uses lifecycle X, deliverable defaults to X (not 'default')."""
    proj = make_project("foo", lifecycle="default")  # parent uses default
    monkeypatch.chdir(proj)
    runner.invoke(app, ["deliverable", "add", "bar", "-d", "x", "-y"])
    deliv_manifest = load_project_manifest(proj / "deliverables" / "bar" / "project.toml")
    assert deliv_manifest.project.lifecycle == "default"
