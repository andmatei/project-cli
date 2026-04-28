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
    result = runner.invoke(app, ["decision", "new", "Some choice", "--no-edit"], catch_exceptions=False)
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
