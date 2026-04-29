"""Tests for `keel design export`."""
from typer.testing import CliRunner

from keel.app import app

runner = CliRunner()


def test_export_deliverable(projects, make_deliverable) -> None:
    """Deliverable-level export produces a single doc with the deliverable's design + decisions."""
    deliv = make_deliverable(project_name="foo", name="bar", description="the bar")
    # Create a decision in the deliverable
    decision_dir = deliv / "design" / "decisions"
    decision_dir.mkdir(parents=True, exist_ok=True)
    (decision_dir / "2026-04-29-pick-x.md").write_text(
        "---\ndate: 2026-04-29\ntitle: Pick X\nstatus: proposed\n---\n# Pick X\n## Question\nQ?\n## Conclusion\nC.\n"
    )
    result = runner.invoke(app, ["design", "export", "--project", "foo", "-D", "bar"])
    assert result.exit_code == 0
    assert "# bar" in result.stdout or "bar" in result.stdout
    assert "Pick X" in result.stdout


def test_export_deliverable_excludes_superseded(projects, make_deliverable) -> None:
    deliv = make_deliverable(project_name="foo", name="bar", description="d")
    decision_dir = deliv / "design" / "decisions"
    decision_dir.mkdir(parents=True, exist_ok=True)
    (decision_dir / "2026-04-29-old.md").write_text(
        "---\ndate: 2026-04-29\ntitle: Old\nstatus: superseded\n---\n# Old\n## Question\nQ?\n## Conclusion\nC.\n"
    )
    (decision_dir / "2026-04-29-new.md").write_text(
        "---\ndate: 2026-04-29\ntitle: New\nstatus: proposed\n---\n# New\n## Question\nQ?\n## Conclusion\nC.\n"
    )
    result = runner.invoke(app, ["design", "export", "--project", "foo", "-D", "bar"])
    assert "New" in result.stdout
    assert "Old" not in result.stdout


def test_export_writes_to_output_file(projects, make_deliverable, tmp_path) -> None:
    make_deliverable(project_name="foo", name="bar", description="d")
    out_path = tmp_path / "out.md"
    result = runner.invoke(app, ["design", "export", "--project", "foo", "-D", "bar", "-o", str(out_path)])
    assert result.exit_code == 0
    assert out_path.is_file()
    assert "bar" in out_path.read_text()


def test_export_project_composes_deliverables(projects, make_project) -> None:
    """Project-level export includes a section per deliverable."""
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "alpha", "-d", "alpha thing", "-y", "--project", "foo"])
    runner.invoke(app, ["deliverable", "add", "beta", "-d", "beta thing", "-y", "--project", "foo"])
    result = runner.invoke(app, ["design", "export", "foo"])
    assert result.exit_code == 0
    assert "## Deliverable: alpha" in result.stdout
    assert "## Deliverable: beta" in result.stdout


def test_export_no_deliverables_flag(projects, make_project) -> None:
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "alpha", "-d", "d", "-y", "--project", "foo"])
    result = runner.invoke(app, ["design", "export", "foo", "--no-deliverables"])
    assert "## Deliverable: alpha" not in result.stdout


def test_export_decision_numbering_flat_across_project(projects, make_project) -> None:
    """Project decisions get D.1+, then deliverable decisions follow."""
    proj_path = projects / "foo"
    make_project("foo")
    runner.invoke(app, ["deliverable", "add", "alpha", "-d", "d", "-y", "--project", "foo"])
    # Add decisions
    (proj_path / "design" / "decisions" / "2026-04-29-p1.md").write_text(
        "---\ndate: 2026-04-29\ntitle: P1\nstatus: proposed\n---\n# P1\n## Question\nQ\n## Conclusion\nC\n"
    )
    deliv_decisions = proj_path / "deliverables" / "alpha" / "design" / "decisions"
    deliv_decisions.mkdir(parents=True, exist_ok=True)
    (deliv_decisions / "2026-04-29-a1.md").write_text(
        "---\ndate: 2026-04-29\ntitle: A1\nstatus: proposed\n---\n# A1\n## Question\nQ\n## Conclusion\nC\n"
    )
    result = runner.invoke(app, ["design", "export", "foo"])
    text = result.stdout
    assert "Appendix D.1: P1" in text
    assert "Appendix D.2:" in text  # deliverable's a1 follows
