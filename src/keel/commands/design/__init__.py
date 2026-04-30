"""`keel design ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="design",
    help="Compose and export design documents.",
    no_args_is_help=True,
)

from keel.commands.design.export import cmd_export  # noqa: E402

app.command(name="export")(cmd_export)
