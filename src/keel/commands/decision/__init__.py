"""`keel decision ...` command group."""
from __future__ import annotations
import typer

app = typer.Typer(
    name="decision",
    help="Manage decision records.",
    no_args_is_help=True,
)

from keel.commands.decision.new import cmd_new
app.command(name="new")(cmd_new)
