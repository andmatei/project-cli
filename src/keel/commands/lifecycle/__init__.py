"""`keel lifecycle ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="lifecycle",
    help="Inspect and manage phase lifecycles.",
    no_args_is_help=True,
)

from keel.commands.lifecycle.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)

from keel.commands.lifecycle.show import cmd_show  # noqa: E402

app.command(name="show")(cmd_show)

from keel.commands.lifecycle.validate import cmd_validate  # noqa: E402

app.command(name="validate")(cmd_validate)
