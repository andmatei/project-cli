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
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress info logs."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose logs."),
) -> None:
    """keel: scope-driven development scaffolder for ~/projects/."""
    if quiet and verbose:
        raise typer.BadParameter("--quiet and --verbose are mutually exclusive.")
    ctx.obj = {"quiet": quiet, "verbose": verbose}


from keel.commands.new import cmd_new  # noqa: E402

app.command(name="new")(cmd_new)

from keel.commands.list import cmd_list  # noqa: E402

app.command(name="list")(cmd_list)

from keel.commands.show import cmd_show  # noqa: E402

app.command(name="show")(cmd_show)

from keel.commands.deliverable import app as deliverable_app  # noqa: E402

app.add_typer(deliverable_app, name="deliverable")

from keel.commands.decision import app as decision_app  # noqa: E402

app.add_typer(decision_app, name="decision")

from keel.commands.phase import cmd_phase  # noqa: E402

app.command(name="phase")(cmd_phase)

from keel.commands.code import app as code_app  # noqa: E402

app.add_typer(code_app, name="code")

from keel.commands.validate import cmd_validate  # noqa: E402

app.command(name="validate")(cmd_validate)

from keel.commands.design import app as design_app  # noqa: E402

app.add_typer(design_app, name="design")

from keel.commands.archive import cmd_archive  # noqa: E402

app.command(name="archive")(cmd_archive)

from keel.commands.rename import cmd_rename  # noqa: E402

app.command(name="rename")(cmd_rename)

from keel.commands.migrate import cmd_migrate  # noqa: E402

app.command(name="migrate")(cmd_migrate)

from keel.commands.completion import cmd_completion  # noqa: E402

app.command(name="completion")(cmd_completion)
