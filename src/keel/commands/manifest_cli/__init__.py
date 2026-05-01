"""`keel manifest ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="manifest",
    help="Lint and inspect manifest files.",
    no_args_is_help=True,
)

from keel.commands.manifest_cli.validate import cmd_validate  # noqa: E402

app.command(name="validate")(cmd_validate)
