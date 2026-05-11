"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator)
- dispatch (manual dispatch, mostly for tests)
- @hookable, hook_event (command-side API) — added in Task 1.6
"""

from __future__ import annotations

from keel.hooks.dispatcher import dispatch
from keel.hooks.registry import subscribes_to
from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
    "dispatch",
    "subscribes_to",
]
