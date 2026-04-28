"""Cross-cutting utilities used by multiple commands."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(name: str) -> str:
    """Lowercase, replace spaces with `-`, drop everything that isn't [a-z0-9-].

    Returns an empty string if the input has no slug-safe characters; callers
    should treat empty-result as invalid input.
    """
    s = name.lower().strip().replace(" ", "-")
    return _SLUG_RE.sub("", s)
