"""`keel code ...` command group — manifest-driven worktree management."""
from __future__ import annotations

import typer

app = typer.Typer(
    name="code",
    help="Manage source-repo linkage and git worktrees.",
    no_args_is_help=True,
)
