"""Lifecycle lookup with precedence: user library → built-ins → plugins (deferred).

Resolution order for `load_lifecycle(name)`:

1. `<PROJECTS_DIR>/.keel/lifecycles/<name>.toml` — the user library.
2. `keel.lifecycles.defaults` package (built-in TOMLs shipped with keel).

Plugin-shipped lifecycles via the `keel.lifecycles` entry-point group are
deferred to a future plan.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

from keel.lifecycles.models import Lifecycle


class LifecycleNotFoundError(LookupError):
    """Raised when no lifecycle with the given name can be found."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name

    def __str__(self) -> str:
        return f"no lifecycle named '{self.name}' (looked in user library and built-ins)"


def _user_library_dir() -> Path:
    """`<PROJECTS_DIR>/.keel/lifecycles/`. Constructed lazily so PROJECTS_DIR can be patched in tests."""
    from keel.workspace import projects_dir

    return projects_dir() / ".keel" / "lifecycles"


def _load_lifecycle_from_path(path: Path, *, expected_name: str | None = None) -> Lifecycle:
    raw = tomllib.loads(path.read_text())
    lc = Lifecycle.model_validate(raw)
    if expected_name is not None and lc.name != expected_name:
        raise LifecycleNotFoundError(expected_name)
    return lc


def load_lifecycle(name: str) -> Lifecycle:
    """Resolve a lifecycle by name through the precedence chain.

    Raises `LifecycleNotFoundError` if no match is found, or if a candidate
    file's `name` field disagrees with its filename stem.
    """
    user_path = _user_library_dir() / f"{name}.toml"
    if user_path.is_file():
        return _load_lifecycle_from_path(user_path, expected_name=name)

    builtin_dir = resources.files("keel.lifecycles.defaults")
    builtin_file = builtin_dir.joinpath(f"{name}.toml")
    if builtin_file.is_file():
        text = builtin_file.read_text()
        raw = tomllib.loads(text)
        lc = Lifecycle.model_validate(raw)
        if lc.name != name:
            raise LifecycleNotFoundError(name)
        return lc

    raise LifecycleNotFoundError(name)


def iter_lifecycles() -> Iterator[Lifecycle]:
    """Yield every reachable lifecycle. User-library entries override built-ins."""
    seen: set[str] = set()

    user_dir = _user_library_dir()
    if user_dir.is_dir():
        for path in sorted(user_dir.glob("*.toml")):
            try:
                lc = _load_lifecycle_from_path(path, expected_name=path.stem)
            except Exception:
                continue
            if lc.name in seen:
                continue
            seen.add(lc.name)
            yield lc

    builtin_dir = resources.files("keel.lifecycles.defaults")
    for entry in sorted(builtin_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".toml"):
            continue
        text = entry.read_text()
        try:
            raw = tomllib.loads(text)
            lc = Lifecycle.model_validate(raw)
        except Exception:
            continue
        if lc.name in seen:
            continue
        seen.add(lc.name)
        yield lc
