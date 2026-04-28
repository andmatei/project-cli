"""AST-aware markdown editing for cross-file mutations.

Uses markdown-it-py to parse so we can target sections by heading text rather
than fragile regex. The implementation is line-based on top of the AST: we
identify the (start, end) line ranges of each top-level (h2) heading section,
then splice text into those ranges.
"""
from __future__ import annotations
from dataclasses import dataclass
from markdown_it import MarkdownIt


_MD = MarkdownIt("commonmark")


@dataclass(frozen=True)
class _Section:
    heading_level: int
    title: str
    heading_line: int  # 0-indexed line number of the heading itself
    body_start: int  # first line of body (heading_line + 1)
    body_end: int  # exclusive: first line of next same-or-higher-level heading or EOF


def _find_sections(text: str, level: int = 2) -> list[_Section]:
    """Return all sections at the given heading level."""
    lines = text.splitlines(keepends=True)
    tokens = _MD.parse(text)
    sections: list[_Section] = []
    pending: tuple[int, str, int] | None = None  # (heading_line, title, start_token_idx)

    def _close(end_line: int) -> None:
        nonlocal pending
        if pending is None:
            return
        heading_line, title, _ = pending
        sections.append(_Section(
            heading_level=level,
            title=title,
            heading_line=heading_line,
            body_start=heading_line + 1,
            body_end=end_line,
        ))
        pending = None

    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            tok_level = int(tok.tag[1:])
            if tok_level <= level:
                # close any open section at this point
                if tok.map is not None:
                    _close(tok.map[0])
            if tok_level == level:
                # title is the inline_text in the next token
                inline = tokens[i + 1]
                title = inline.content.strip()
                heading_line = tok.map[0]
                pending = (heading_line, title, i)
    _close(len(lines))
    return sections


def section_exists(text: str, title: str) -> bool:
    return any(s.title == title for s in _find_sections(text))


def _ensure_trailing_newline(s: str) -> str:
    return s if s.endswith("\n") else s + "\n"


def insert_under_heading(text: str, title: str, line_to_insert: str) -> str:
    """Insert a line under the section with `title`. Idempotent — no duplicates.

    If the section doesn't exist, create it at the end of the document.
    """
    line_to_insert = _ensure_trailing_newline(line_to_insert)
    text = _ensure_trailing_newline(text)
    sections = _find_sections(text)
    target = next((s for s in sections if s.title == title), None)
    if target is None:
        # Append a new section
        return text + f"\n## {title}\n{line_to_insert}"
    lines = text.splitlines(keepends=True)
    body_lines = lines[target.body_start:target.body_end]
    if any(b == line_to_insert for b in body_lines):
        return text  # already present, idempotent
    # Insert after the last non-empty body line, or right after the heading if body is empty
    insert_at = target.body_start
    for j in range(target.body_end - 1, target.body_start - 1, -1):
        if lines[j].strip():
            insert_at = j + 1
            break
    new_lines = lines[:insert_at] + [line_to_insert] + lines[insert_at:]
    return "".join(new_lines)


def replace_section(text: str, title: str, new_body: str) -> str:
    """Replace the body of a section. If the section doesn't exist, append it."""
    new_body = _ensure_trailing_newline(new_body)
    text = _ensure_trailing_newline(text)
    sections = _find_sections(text)
    target = next((s for s in sections if s.title == title), None)
    if target is None:
        return text + f"\n## {title}\n{new_body}"
    lines = text.splitlines(keepends=True)
    head = lines[:target.body_start]
    tail = lines[target.body_end:]
    return "".join(head) + new_body + ("\n" if not new_body.endswith("\n\n") else "") + "".join(tail)


def remove_line_under_heading(text: str, title: str, line_to_remove: str) -> str:
    """Remove a specific line from a section's body. No-op if absent."""
    line_to_remove = _ensure_trailing_newline(line_to_remove)
    text = _ensure_trailing_newline(text)
    sections = _find_sections(text)
    target = next((s for s in sections if s.title == title), None)
    if target is None:
        return text
    lines = text.splitlines(keepends=True)
    body = [b for b in lines[target.body_start:target.body_end] if b != line_to_remove]
    return "".join(lines[:target.body_start]) + "".join(body) + "".join(lines[target.body_end:])
