"""Tests for AST-aware markdown editing."""
from __future__ import annotations
import pytest
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
