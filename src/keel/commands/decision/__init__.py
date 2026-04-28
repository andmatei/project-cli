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

from keel.commands.decision.list import cmd_list
app.command(name="list")(cmd_list)

from keel.commands.decision.show import cmd_show
app.command(name="show")(cmd_show)

from keel.commands.decision.rm import cmd_rm
app.command(name="rm")(cmd_rm)
