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
from keel.commands.milestone.show import cmd_show  # noqa: E402

app.command(name="add")(cmd_add)
app.command(name="list")(cmd_list)
app.command(name="show")(cmd_show)

from keel.commands.milestone.start import cmd_start  # noqa: E402

app.command(name="start")(cmd_start)

from keel.commands.milestone.done import cmd_done  # noqa: E402

app.command(name="done")(cmd_done)

from keel.commands.milestone.cancel import cmd_cancel  # noqa: E402

app.command(name="cancel")(cmd_cancel)
