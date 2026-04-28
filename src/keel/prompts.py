"""Interactive-prompt helpers, with non-TTY safety.

The CLI fails loud (exit 2) when a required value is missing on a non-TTY
stdin, rather than hanging on a prompt or silently using a default.
"""

from __future__ import annotations

import sys

import questionary
import typer


def is_interactive() -> bool:
    """True iff stdin is a TTY."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _prompt_text(label: str) -> str:
    return questionary.text(label).unsafe_ask() or ""


def require_or_fail(value: str | None, *, arg_name: str, label: str | None = None) -> str:
    """Return `value` if non-empty; else prompt on TTY, else exit 2."""
    if value:
        return value
    if not is_interactive():
        typer.echo(
            f"error: {arg_name} is required (stdin is not a TTY, cannot prompt)",
            err=True,
        )
        raise typer.Exit(code=2)
    text = _prompt_text(label or arg_name)
    if not text:
        typer.echo(f"error: {arg_name} is required", err=True)
        raise typer.Exit(code=2)
    return text


def confirm_destructive(message: str, *, yes: bool) -> None:
    """Confirm a destructive op. Raises typer.Exit(code=1) on decline.

    `yes=True` skips the prompt. Non-TTY without `yes` also fails.
    """
    if yes:
        return
    if not is_interactive():
        typer.echo(
            "error: refusing to run destructive op without --yes on a non-TTY stdin",
            err=True,
        )
        raise typer.Exit(code=1)
    answer = questionary.confirm(message, default=False).unsafe_ask()
    if not answer:
        typer.echo("Aborted.", err=True)
        raise typer.Exit(code=1)
