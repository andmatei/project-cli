"""`keel code ...` command group — manifest-driven worktree management."""
from __future__ import annotations

import typer

app = typer.Typer(
    name="code",
    help="Manage source-repo linkage and git worktrees.",
    no_args_is_help=True,
)

from keel.commands.code.list import cmd_list  # noqa: E402
app.command(name="list")(cmd_list)

from keel.commands.code.status import cmd_status  # noqa: E402
app.command(name="status")(cmd_status)
