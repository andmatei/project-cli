"""`keel lifecycle list` — enumerate available lifecycles."""

from __future__ import annotations

import typer
from rich.table import Table

from keel.api import Output, iter_lifecycles
from keel.workspace import projects_dir


def _source_for(name: str) -> str:
    """Return 'user' if the user library has a TOML for this name, else 'builtin'."""
    user_path = projects_dir() / ".keel" / "lifecycles" / f"{name}.toml"
    if user_path.is_file():
        return "user"
    return "builtin"


def cmd_list(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """List all available lifecycles (built-ins + user library)."""
    out = Output.from_context(ctx, json_mode=json_mode)

    rows: list[dict[str, str]] = []
    for lc in iter_lifecycles():
        rows.append(
            {
                "name": lc.name,
                "description": lc.description,
                "source": _source_for(lc.name),
                "states": str(len(lc.states)),
                "initial": lc.initial,
            }
        )

    if json_mode:
        out.result({"lifecycles": rows})
        return

    table = Table()
    table.add_column("Name")
    table.add_column("Source")
    table.add_column("States")
    table.add_column("Initial")
    table.add_column("Description")
    for r in rows:
        table.add_row(r["name"], r["source"], r["states"], r["initial"], r["description"])
    out.print_rich(table)
