"""In-tree subscriber registry.

Built-in keel modules call `@subscribes_to("pre-X")` at import time to
register themselves. The registry is process-global; tests reset it
between runs via `_clear_registry()`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from keel.hooks.types import HookEvent


Subscriber = Callable[["HookEvent"], None]
"""A subscriber is a callable receiving HookEvent + Output kwarg. See dispatcher."""


_REGISTRY: dict[str, list[Subscriber]] = {}


def subscribes_to(event_full_name: str) -> Callable[[Subscriber], Subscriber]:
    """Decorator: register an in-tree subscriber for a given event name.

    `event_full_name` MUST start with 'pre-' or 'post-'. Examples:
    'pre-new', 'post-phase', 'pre-deliverable-add'.

    The decorated function receives the HookEvent and an Output kwarg,
    and returns None. It may raise HookAborted (pre-events only) to abort.
    """
    if not (event_full_name.startswith("pre-") or event_full_name.startswith("post-")):
        raise ValueError(f"event name '{event_full_name}' must start with 'pre-' or 'post-'")

    def _register(fn: Subscriber) -> Subscriber:
        _REGISTRY.setdefault(event_full_name, []).append(fn)
        return fn

    return _register


def iter_in_tree_subscribers(event_full_name: str) -> Iterator[Subscriber]:
    """Yield in-tree subscribers for the given event in registration order."""
    yield from _REGISTRY.get(event_full_name, [])


def _clear_registry() -> None:
    """Test-only: empty the registry. Not part of the public API."""
    _REGISTRY.clear()
