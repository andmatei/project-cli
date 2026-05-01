"""`keel plugin ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="plugin",
    help="Inspect installed keel plugins and their configuration.",
    no_args_is_help=True,
)

from keel.commands.plugin.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)

from keel.commands.plugin.doctor import cmd_doctor  # noqa: E402

app.command(name="doctor")(cmd_doctor)
