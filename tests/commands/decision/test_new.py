"""Tests for `keel decision new`."""

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_new_creates_decision_file_at_project_level(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app,
        ["decision", "new", "Use Pydantic v2", "--no-edit"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stderr
    decisions = list((proj / "design" / "decisions").glob("*.md"))
    decision_files = [f for f in decisions if "use-pydantic-v2" in f.name]
    assert len(decision_files) == 1


def test_new_at_deliverable_level(projects, make_deliverable, monkeypatch) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    monkeypatch.chdir(deliv / "design")
    result = runner.invoke(
        app, ["decision", "new", "Some choice", "--no-edit"], catch_exceptions=False
    )
    assert result.exit_code == 0
    decision_files = list((deliv / "design" / "decisions").glob("*-some-choice.md"))
    assert len(decision_files) == 1


def test_new_writes_frontmatter_and_template(projects, make_project, monkeypatch) -> None:
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["decision", "new", "Pick a thing", "--no-edit"])
    decision_files = list((proj / "design" / "decisions").glob("*-pick-a-thing.md"))
    body = decision_files[0].read_text()
    assert "title: Pick a thing" in body
    assert "status: proposed" in body
    assert "## Question" in body


def test_new_fails_if_no_scope(projects, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["decision", "new", "X", "--no-edit"])
    assert result.exit_code == 1
    assert "no project" in result.stderr.lower()


def test_new_supersedes_marks_old_decision(projects, make_project, monkeypatch) -> None:
    """--supersedes should mark the old decision as superseded and link to the new one."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    runner.invoke(app, ["decision", "new", "Old choice", "--no-edit"])
    old_files = list((proj / "design" / "decisions").glob("*-old-choice.md"))
    assert len(old_files) == 1

    runner.invoke(app, ["decision", "new", "New choice", "--no-edit", "--supersedes", "old-choice"])
    new_files = list((proj / "design" / "decisions").glob("*-new-choice.md"))
    assert len(new_files) == 1
    new_slug = new_files[0].stem

    old_body = old_files[0].read_text()
    assert "status: superseded" in old_body
    assert new_slug in old_body  # references the new decision


def test_new_supersedes_wrong_slug_fails_loud(projects, make_project, monkeypatch) -> None:
    """--supersedes with no matching decision must exit 1 and not create the new decision."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(
        app,
        ["decision", "new", "New choice", "--no-edit", "--supersedes", "nonexistent-decision"],
    )
    assert result.exit_code == 1
    # New decision file should NOT have been created
    new_files = list((proj / "design" / "decisions").glob("*-new-choice.md"))
    assert new_files == []


def test_new_does_not_print_duplicate_messages(projects, make_project, monkeypatch) -> None:
    """'Created decision: ...' (stderr) was redundant with 'Decision created: ...' (stdout)."""
    proj = make_project("foo")
    monkeypatch.chdir(proj / "design")
    result = runner.invoke(app, ["decision", "new", "Some choice", "--no-edit"])
    assert "Created decision:" not in result.stderr
    assert result.stdout  # non-empty
