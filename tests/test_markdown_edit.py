"""Tests for AST-aware markdown editing."""

from __future__ import annotations

from keel.markdown_edit import (
    insert_under_heading,
    replace_section,
    section_exists,
)

SAMPLE = """# Title

Intro paragraph.

## Workflow

- Do thing A
- Do thing B

## References

- ref 1
"""


def test_section_exists_true() -> None:
    assert section_exists(SAMPLE, "Workflow") is True


def test_section_exists_false() -> None:
    assert section_exists(SAMPLE, "Deliverables") is False


def test_insert_under_existing_heading_appends() -> None:
    out = insert_under_heading(SAMPLE, "Workflow", "- Do thing C\n")
    assert "- Do thing C" in out
    # Existing items still present:
    assert "- Do thing A" in out
    # Inserted under Workflow, not References:
    workflow_idx = out.index("## Workflow")
    refs_idx = out.index("## References")
    assert workflow_idx < out.index("- Do thing C") < refs_idx


def test_insert_under_missing_heading_creates_it() -> None:
    out = insert_under_heading(SAMPLE, "Deliverables", "- bar: ../d/bar/\n")
    assert "## Deliverables" in out
    assert "- bar: ../d/bar/" in out


def test_insert_is_idempotent() -> None:
    """Re-inserting an identical line under a heading does not duplicate."""
    once = insert_under_heading(SAMPLE, "Workflow", "- Do thing C\n")
    twice = insert_under_heading(once, "Workflow", "- Do thing C\n")
    assert twice == once


def test_replace_section_swaps_body() -> None:
    out = replace_section(SAMPLE, "Workflow", "- Replaced\n")
    assert "- Replaced" in out
    assert "- Do thing A" not in out
    # Other sections untouched:
    assert "## References" in out
    assert "- ref 1" in out


def test_replace_section_missing_heading_appends() -> None:
    out = replace_section(SAMPLE, "Deliverables", "- foo\n")
    assert "## Deliverables" in out
    assert "- foo" in out


def test_remove_line_under_heading() -> None:
    """Removing a specific line preserves other content under the heading."""
    from keel.markdown_edit import remove_line_under_heading

    out = remove_line_under_heading(SAMPLE, "Workflow", "- Do thing A\n")
    assert "- Do thing A" not in out
    assert "- Do thing B" in out


def test_replace_section_is_idempotent_on_re_apply() -> None:
    """Re-applying the same body produces identical output (no whitespace drift)."""
    text = """# Title

Intro.

## Section A

- existing item
"""
    once = replace_section(text, "Section A", "- new item\n")
    twice = replace_section(once, "Section A", "- new item\n")
    assert once == twice


def test_replace_section_preserves_blank_line_before_next_heading() -> None:
    """After replacement, there's exactly one blank line between body and next heading."""
    text = """# Title

## A

- old

## B

content
"""
    out = replace_section(text, "A", "- new\n")
    assert "## A\n- new\n" in out or "## A\n\n- new\n" in out
    # Crucially: no triple-newline before "## B"
    assert "\n\n\n## B" not in out


def test_remove_bullet_by_prefix() -> None:
    """Remove all body lines under a section that start with the given prefix."""
    text = """# Title

## Deliverables

- **alpha**: ../deliverables/alpha/design/ -- the alpha
- **beta**: ../deliverables/beta/design/ -- the beta
- **gamma**: ../deliverables/gamma/design/ -- the gamma

## Other
"""
    from keel.markdown_edit import remove_bullet_under_heading

    out = remove_bullet_under_heading(text, "Deliverables", "- **beta**:")
    assert "**beta**" not in out
    assert "**alpha**" in out
    assert "**gamma**" in out
    assert "## Other" in out


def test_remove_bullet_no_match_is_noop() -> None:
    text = "# T\n\n## D\n- **a**: x\n"
    from keel.markdown_edit import remove_bullet_under_heading

    out = remove_bullet_under_heading(text, "D", "- **z**:")
    assert out == text


def test_replace_section_appends_with_consistent_spacing() -> None:
    """When the section doesn't exist, the appended section is well-spaced."""
    text = "# Title\n\n## A\n- a\n"
    out = replace_section(text, "B", "- b\n")
    # Existing "## A" body intact:
    assert "## A\n- a\n" in out
    # New "## B" appended with at most one blank line before it:
    assert "\n## B\n- b\n" in out
    assert "\n\n\n## B" not in out
