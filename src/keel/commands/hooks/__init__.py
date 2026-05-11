"""`keel hooks ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="hooks",
    help="Manage user-script hooks at `.keel/hooks/`.",
    no_args_is_help=True,
)

from keel.commands.hooks.init import cmd_init  # noqa: E402

app.command(name="init")(cmd_init)
