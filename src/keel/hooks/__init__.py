"""keel hooks framework — events, dispatcher, subscriber registry.

Public API:
- HookEvent, HookAborted (types)
- subscribes_to (in-tree subscriber decorator) — added in Task 1.2
- @hookable, hook_event (command-side API) — added in Task 1.6
- dispatch (manual dispatch, mostly for tests) — added in Task 1.5
"""

from __future__ import annotations

from keel.hooks.types import HookAborted, HookEvent

__all__ = [
    "HookAborted",
    "HookEvent",
]
