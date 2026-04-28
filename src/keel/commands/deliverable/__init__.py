"""`keel deliverable ...` command group."""
from __future__ import annotations
import typer

app = typer.Typer(
    name="deliverable",
    help="Manage deliverables (mini-projects nested under a project).",
    no_args_is_help=True,
)

from keel.commands.deliverable.add import cmd_add
app.command(name="add")(cmd_add)
