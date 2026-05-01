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

from keel.commands.task.graph import cmd_graph  # noqa: E402

app.command(name="graph")(cmd_graph)

from keel.commands.task.rm import cmd_rm  # noqa: E402

app.command(name="rm")(cmd_rm)

from keel.commands.task.worktree import cmd_worktree  # noqa: E402

app.command(name="worktree")(cmd_worktree)

from keel.commands.task.next import cmd_next  # noqa: E402

app.command(name="next")(cmd_next)
