"""Unified output for human + JSON modes.

Conventions:
- stdout: command results (human text or JSON payload)
- stderr: progress/info logs, errors, prompts
- --json implies --quiet
"""
from __future__ import annotations
import json
import sys
from typing import Any
from rich.console import Console


class Output:
    def __init__(self, quiet: bool = False, verbose: bool = False, json_mode: bool = False) -> None:
        if json_mode:
            quiet = True
        self.quiet = quiet
        self.verbose = verbose
        self.json_mode = json_mode
        # soft_wrap=True so long paths/words aren't broken across lines —
        # callers (and tests) match on substrings like "project.toml" and
        # rely on the terminal to do its own wrapping.
        self._stderr = Console(file=sys.stderr, highlight=False, soft_wrap=True)
        self._stdout = Console(file=sys.stdout, highlight=False, soft_wrap=True)

    def info(self, message: str) -> None:
        if not self.quiet:
            self._stderr.print(message, markup=False)

    def warn(self, message: str) -> None:
        if not self.quiet:
            self._stderr.print(f"[yellow]{message}[/yellow]")

    def error(self, message: str, code: str | None = None) -> None:
        if self.json_mode:
            payload: dict[str, Any] = {"error": message}
            if code:
                payload["code"] = code
            self._stderr.print(json.dumps(payload))
        else:
            self._stderr.print(f"[red]error:[/red] {message}")

    def debug(self, message: str) -> None:
        if self.verbose:
            self._stderr.print(f"[dim]{message}[/dim]")

    def print_rich(self, renderable) -> None:
        """Print a Rich renderable to stdout (only in human mode)."""
        if not self.json_mode:
            self._stdout.print(renderable)

    @classmethod
    def from_context(cls, ctx, *, json_mode: bool = False) -> "Output":
        """Build an Output instance using global --quiet/--verbose flags from a Typer context."""
        obj = (ctx.obj or {}) if hasattr(ctx, "obj") else {}
        return cls(
            quiet=obj.get("quiet", False),
            verbose=obj.get("verbose", False),
            json_mode=json_mode,
        )

    def result(self, payload: Any, *, human_text: str | None = None) -> None:
        """Emit a command result.

        - JSON mode: writes `payload` as JSON to stdout.
        - Human mode: writes `human_text` (defaults to repr(payload)) to stdout.
        """
        if self.json_mode:
            print(json.dumps(payload, default=str))
        else:
            text = human_text if human_text is not None else repr(payload)
            self._stdout.print(text)
