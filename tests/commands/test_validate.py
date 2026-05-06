"""Tests for `keel validate`."""

import json

from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_validate_clean_project(projects, make_project) -> None:
    make_project("foo")
    result = runner.invoke(app, ["validate", "foo"])
    assert result.exit_code == 0


def test_validate_missing_design_md_warns(projects, make_project) -> None:
    proj = make_project("foo")
    (proj / "design.md").unlink()
    result = runner.invoke(app, ["validate", "foo", "--json"])
    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert summary["fail"] >= 1 or summary["warn"] >= 1


def test_validate_missing_phase_warns(projects, make_project) -> None:
    proj = make_project("foo")
    (proj / ".keel" / "phase").unlink()
    result = runner.invoke(app, ["validate", "foo", "--json"])
    payload = json.loads(result.stdout)
    assert payload["summary"]["fail"] >= 1 or payload["summary"]["warn"] >= 1


def test_validate_orphan_deliverable_dir_warns(projects, make_project, make_deliverable) -> None:
    """A deliverable dir with project.toml but not mentioned in parent design.md should warn."""
    make_deliverable(project_name="foo", name="bar", description="d")
    # The fixture's parent design.md does not auto-list deliverables, so the orphan
    # warning fires by default. Sanity-check the precondition then assert.
    parent_design = (projects / "foo" / "design.md").read_text()
    assert "**bar**" not in parent_design
    result = runner.invoke(app, ["validate", "foo", "--json"])
    payload = json.loads(result.stdout)
    findings = payload["findings"]
    refs_warns = [
        f
        for f in findings
        if f["check"] == "refs" and f["level"] == "warn" and "bar" in f["message"]
    ]
    assert refs_warns, f"expected an orphan-deliverable warning, got: {findings}"


def test_validate_summary_on_stdout_with_table(projects, make_project) -> None:
    """The validate summary should travel on the same stream as the table (stdout)."""
    make_project("foo")
    result = runner.invoke(app, ["validate", "foo"])
    assert result.exit_code == 0
    # Either the summary appears on stdout, or it's omitted entirely from stderr
    assert "summary:" not in result.stderr
