"""Top-level Typer app and global flags."""
from __future__ import annotations
import typer
from keel import __version__

app = typer.Typer(
    name="keel",
    help="Manage the ~/projects/ workspace.",
    no_args_is_help=True,
    add_completion=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress info logs."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose logs."),
) -> None:
    """keel: manage the ~/projects/ workspace."""
    if quiet and verbose:
        raise typer.BadParameter("--quiet and --verbose are mutually exclusive.")


from keel.commands.new import cmd_new
app.command(name="new")(cmd_new)

from keel.commands.list import cmd_list
app.command(name="list")(cmd_list)

from keel.commands.show import cmd_show
app.command(name="show")(cmd_show)

from keel.commands.deliverable import app as deliverable_app
app.add_typer(deliverable_app, name="deliverable")

from keel.commands.decision import app as decision_app
app.add_typer(decision_app, name="decision")
