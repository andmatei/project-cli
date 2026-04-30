"""`keel milestone ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="milestone",
    help="Manage milestones (groups of work scoped to a project or deliverable).",
    no_args_is_help=True,
)

from keel.commands.milestone.add import cmd_add  # noqa: E402
from keel.commands.milestone.list import cmd_list  # noqa: E402

app.command(name="add")(cmd_add)
app.command(name="list")(cmd_list)
