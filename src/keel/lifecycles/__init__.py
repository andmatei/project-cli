"""Customizable phase lifecycles for keel.

The `default` lifecycle (the original 6 phases) ships in
`keel/lifecycles/defaults/default.toml`. Users can add their own under
`~/projects/.keel/lifecycles/<name>.toml`.
"""

from __future__ import annotations

from keel.lifecycles.models import Lifecycle, LifecycleState

__all__ = ["Lifecycle", "LifecycleState"]
