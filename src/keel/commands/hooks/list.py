"""`keel hooks list`."""

from __future__ import annotations

import typer
from rich.table import Table

from keel.api import Output
from keel.hooks.hookable import registered_events
from keel.hooks.registry import _REGISTRY


def cmd_list(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="Emit machine-readable JSON to stdout."),
) -> None:
    """List all events keel commands can fire, along with subscribers."""
    out = Output.from_context(ctx, json_mode=json_mode)

    # Trigger plugin entry-point load so we see plugin subscribers too.
    from keel.hooks.dispatcher import _ensure_plugins_loaded

    _ensure_plugins_loaded()

    # Also register the built-in pre-phase listeners (idempotent).
    from keel.hooks.builtin_listeners import register_builtin_listeners

    register_builtin_listeners()

    events = sorted(registered_events())
    payload: dict[str, dict] = {}
    for event_name in events:
        pre_subs = [_fmt_subscriber(s) for s in _REGISTRY.get(f"pre-{event_name}", [])]
        post_subs = [_fmt_subscriber(s) for s in _REGISTRY.get(f"post-{event_name}", [])]
        payload[event_name] = {
            "pre_subscribers": pre_subs,
            "post_subscribers": post_subs,
        }
    # Also surface any extra subscribers for events that aren't in registered_events
    # (e.g. plugins subscribing to events keel-cli doesn't fire).
    extra_keys = {k for k in _REGISTRY if k.split("-", 1)[1] not in events}
    extra_subs = {k: [_fmt_subscriber(s) for s in _REGISTRY[k]] for k in extra_keys}

    if json_mode:
        out.result(
            {
                "events": payload,
                "extra_subscribers": extra_subs,
            }
        )
        return

    table = Table()
    table.add_column("Event")
    table.add_column("Pre subscribers")
    table.add_column("Post subscribers")
    for event_name in events:
        e = payload[event_name]
        table.add_row(
            event_name,
            "\n".join(e["pre_subscribers"]) or "—",
            "\n".join(e["post_subscribers"]) or "—",
        )
    out.print_rich(table)
    if extra_subs:
        out.info(
            "Note: plugin subscribers registered for events not fired by built-in commands: "
            + ", ".join(sorted(extra_subs.keys()))
        )


def _fmt_subscriber(fn) -> str:
    """Format a subscriber callable as 'module.qualname'."""
    mod = getattr(fn, "__module__", "?")
    name = getattr(fn, "__qualname__", getattr(fn, "__name__", "?"))
    return f"{mod}.{name}"
