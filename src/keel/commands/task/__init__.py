"""`keel task ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="task",
    help="Manage tasks (atomic units of work under a milestone, with DAG dependencies).",
    no_args_is_help=True,
)

from keel.commands.task.add import cmd_add  # noqa: E402
from keel.commands.task.list import cmd_list  # noqa: E402

app.command(name="add")(cmd_add)
app.command(name="list")(cmd_list)
