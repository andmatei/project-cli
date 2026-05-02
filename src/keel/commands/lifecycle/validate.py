"""`keel lifecycle validate <path>` — lint a lifecycle TOML offline."""

from __future__ import annotations

import tomllib
from pathlib import Path

import typer

from keel.api import ErrorCode, Output
from keel.lifecycles.models import Lifecycle


def cmd_validate(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Path to a lifecycle TOML."),
    json_mode: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON to stdout."
    ),
) -> None:
    """Validate a lifecycle TOML against the Lifecycle schema."""
    out = Output.from_context(ctx, json_mode=json_mode)

    if not path.is_file():
        out.fail(f"file not found: {path}", code=ErrorCode.NOT_FOUND)

    try:
        raw = tomllib.loads(path.read_text())
    except Exception as e:
        out.fail(f"invalid TOML: {e}", code=ErrorCode.INVALID_STATE)

    try:
        lc = Lifecycle.model_validate(raw)
    except Exception as e:
        out.fail(f"lifecycle invalid: {e}", code=ErrorCode.INVALID_STATE)

    if lc.name != path.stem:
        out.warn(
            f"lifecycle name '{lc.name}' does not match filename stem '{path.stem}' "
            "(load_lifecycle would not find this file by '{path.stem}')"
        )

    out.result(
        {"path": str(path), "name": lc.name, "valid": True},
        human_text=f"OK — lifecycle valid: {lc.name} ({path})",
    )
