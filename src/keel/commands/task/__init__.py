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

from keel.commands.task.show import cmd_show  # noqa: E402

app.command(name="show")(cmd_show)

from keel.commands.task.start import cmd_start  # noqa: E402

app.command(name="start")(cmd_start)

from keel.commands.task.done import cmd_done  # noqa: E402

app.command(name="done")(cmd_done)

from keel.commands.task.cancel import cmd_cancel  # noqa: E402

app.command(name="cancel")(cmd_cancel)
