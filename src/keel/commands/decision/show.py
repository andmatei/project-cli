"""`keel decision show <slug>`."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.markdown import Markdown

from keel import workspace
from keel.output import Output

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    body = text[m.end() :]
    return fm, body


def _find_decision(decisions_dir: Path, slug: str) -> Path | None:
    """Find a decision file by slug or full filename."""
    if slug.endswith(".md"):
        candidate = decisions_dir / slug
        return candidate if candidate.is_file() else None
    matches = list(decisions_dir.glob(f"*-{slug}.md"))
    if matches:
        return matches[0]
    return None


def cmd_show(
    ctx: typer.Context,
    slug: str = typer.Argument(..., help="Decision slug (date prefix optional) or full filename."),
    deliverable: str | None = typer.Option(
        None,
        "-D",
        "--deliverable",
        help="Decision scope: a deliverable instead of the project. Auto-detected from CWD.",
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Parent project. Auto-detected from CWD if omitted."
    ),
    raw: bool = typer.Option(
        False, "--raw", help="Print the raw file contents unchanged (pipe-friendly)."
    ),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show a decision record."""
    out = Output.from_context(ctx, json_mode=json_mode)

    from keel.workspace import resolve_cli_scope

    scope = resolve_cli_scope(project, deliverable)
    project = scope.project
    deliverable = scope.deliverable

    target_dir = workspace.decisions_dir(project, deliverable)

    path = _find_decision(target_dir, slug)
    if path is None:
        from keel.errors import HINT_LIST_DECISIONS
        out.error(f"decision not found: {slug}\n  {HINT_LIST_DECISIONS}", code="not_found")
        raise typer.Exit(code=1)

    text = path.read_text()
    fm, body = _split_frontmatter(text)

    if json_mode:
        out.result(
            {
                "path": str(path),
                "frontmatter": fm,
                "body_markdown": body,
            }
        )
        return

    if raw:
        out.result(None, human_text=text.rstrip("\n"))
        return

    out.print_rich(Markdown(body))
