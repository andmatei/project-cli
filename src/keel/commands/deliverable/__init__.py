"""`keel deliverable ...` command group."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="deliverable",
    help="Manage deliverables (mini-projects nested under a project).",
    no_args_is_help=True,
)

from keel.commands.deliverable.add import cmd_add  # noqa: E402

app.command(name="add")(cmd_add)

from keel.commands.deliverable.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)

from keel.commands.deliverable.rm import cmd_rm  # noqa: E402

app.command(name="rm")(cmd_rm)

from keel.commands.deliverable.rename import cmd_rename  # noqa: E402

app.command(name="rename")(cmd_rename)
