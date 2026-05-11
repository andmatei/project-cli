"""Plugin entry-point loader for keel.event_listeners.

A plugin declares its subscribers via:

    [project.entry-points."keel.event_listeners"]
    on_new = "my_pkg.listeners:on_project_created"

Each entry-point value imports a function decorated with @subscribes_to,
which side-effects the in-tree registry. Loading is idempotent because
Python's import machinery caches modules.
"""

from __future__ import annotations

import sys
from importlib.metadata import entry_points

ENTRY_POINT_GROUP = "keel.event_listeners"


def load_plugin_listeners() -> None:
    """Discover all plugin event listeners and import them.

    Errors loading any single entry point are reported to stderr but never
    raised — one broken plugin must not crash keel. Subsequent entry
    points still load.
    """
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            ep.load()
        except Exception as e:  # noqa: BLE001
            print(
                f"warning: failed to load event listener '{ep.name}': {e}",
                file=sys.stderr,
            )
