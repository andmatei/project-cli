"""Tests for the template renderer."""
from project_cli.templates import render


def test_render_claude_md() -> None:
    out = render(
        "claude_md.j2",
        name="foo",
        description="A test project",
        repos=[],
        deliverables=[],
    )
    assert "# foo" in out
    assert "A test project" in out


def test_render_scope_md() -> None:
    out = render("scope_md.j2", name="foo", description="A test project")
    assert "# foo" in out
    assert "Scope Document" in out


def test_render_design_md() -> None:
    out = render("design_md.j2", name="foo", description="A test project")
    assert "# foo" in out


def test_render_decision_entry() -> None:
    out = render(
        "decision_entry.j2",
        date="2026-04-27",
        title="Pick a thing",
    )
    assert "# Pick a thing" in out
    assert "status: proposed" in out
    assert "2026-04-27" in out


def test_render_claude_md_with_repos() -> None:
    out = render(
        "claude_md.j2",
        name="foo",
        description="d",
        repos=[{"worktree": "code", "remote": "git@github.com:org/r.git"}],
        deliverables=[],
    )
    assert "## Code" in out
    assert "code" in out
    assert "git@github.com:org/r.git" in out


def test_render_claude_md_with_deliverables() -> None:
    out = render(
        "claude_md.j2",
        name="foo",
        description="d",
        repos=[],
        deliverables=[{"name": "bar", "description": "the bar"}],
    )
    assert "## Deliverables" in out
    assert "bar" in out


def test_render_claude_md_no_triple_blank_lines() -> None:
    """Avoid triple blank lines in any rendered combination."""
    cases = [
        {"repos": [], "deliverables": []},
        {"repos": [{"worktree": "code", "remote": "g@h:o/r.git", "local_hint": None}], "deliverables": []},
        {"repos": [], "deliverables": [{"name": "bar", "description": "the bar"}]},
        {"repos": [{"worktree": "code", "remote": "g@h:o/r.git", "local_hint": None}],
         "deliverables": [{"name": "bar", "description": "the bar"}]},
    ]
    for ctx in cases:
        out = render("claude_md.j2", name="foo", description="d", **ctx)
        assert "\n\n\n" not in out, f"triple blank lines in output for ctx={ctx}:\n{out}"
