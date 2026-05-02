"""`keel lifecycle show <name>` — print a lifecycle's states and transitions."""

from __future__ import annotations

import typer
from rich.table import Table

from keel.api import (
    ErrorCode,
    LifecycleNotFoundError,
    Output,
    load_lifecycle,
)


def cmd_show(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Lifecycle name."),
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """Show a lifecycle's states, terminal set, and transitions."""
    out = Output.from_context(ctx, json_mode=json_mode)
    try:
        lc = load_lifecycle(name)
    except LifecycleNotFoundError as e:
        out.fail(str(e), code=ErrorCode.NOT_FOUND)

    if json_mode:
        out.result(lc.model_dump())
        return

    out.info(f"Lifecycle: {lc.name}")
    if lc.description:
        out.info(f"  {lc.description}")
    out.info(f"Initial: {lc.initial}")
    out.info(f"Terminal: {', '.join(lc.terminal)}")

    table = Table(title="Transitions")
    table.add_column("From")
    table.add_column("To")
    for src in lc.states:
        succs = lc.successors(src)
        if not succs:
            continue
        table.add_row(src, ", ".join(succs))
    out.print_rich(table)
