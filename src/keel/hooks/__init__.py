"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator)
- dispatch (manual dispatch, mostly for tests)
- hookable, hook_event (command-side API)
"""

from __future__ import annotations

from keel.hooks.dispatcher import dispatch
from keel.hooks.hookable import hook_event, hookable, registered_events
from keel.hooks.registry import subscribes_to
from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
    "dispatch",
    "hook_event",
    "hookable",
    "registered_events",
    "subscribes_to",
]
