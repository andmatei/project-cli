"""Tests for the lifecycle loader (precedence + iteration)."""

import pytest

from keel.lifecycles import (
    Lifecycle,
    LifecycleNotFoundError,
    iter_lifecycles,
    load_lifecycle,
)


def test_load_default_from_builtin(projects) -> None:
    """`load_lifecycle('default')` returns the built-in shipped TOML."""
    lc = load_lifecycle("default")
    assert isinstance(lc, Lifecycle)
    assert lc.name == "default"
    assert lc.initial == "scoping"


def test_load_unknown_raises_lifecycle_not_found(projects) -> None:
    with pytest.raises(LifecycleNotFoundError) as exc:
        load_lifecycle("does-not-exist")
    assert "does-not-exist" in str(exc.value)


def test_load_from_user_library(projects) -> None:
    """A TOML at `<projects>/.keel/lifecycles/<name>.toml` is found."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        """
name = "research"
description = "Research project lifecycle."
initial = "proposing"
terminal = ["published", "cancelled"]

[states.proposing]
[states.reviewing]
[states.executing]
[states.published]
[states.cancelled]

[transitions]
proposing = ["reviewing"]
reviewing = ["executing", "proposing"]
executing = ["published"]
""".strip()
    )
    lc = load_lifecycle("research")
    assert lc.name == "research"
    assert lc.initial == "proposing"


def test_user_library_overrides_builtin(projects) -> None:
    """A user-library file with the same name as a built-in wins."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "default.toml").write_text(
        """
name = "default"
description = "Custom default."
initial = "x"
terminal = ["y"]

[states.x]
[states.y]

[transitions]
x = ["y"]
""".strip()
    )
    lc = load_lifecycle("default")
    # User library wins
    assert lc.initial == "x"
    assert lc.description == "Custom default."


def test_iter_lifecycles_includes_default(projects) -> None:
    items = list(iter_lifecycles())
    names = {lc.name for lc in items}
    assert "default" in names


def test_iter_lifecycles_includes_user_library(projects) -> None:
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        """
name = "research"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
""".strip()
    )
    items = list(iter_lifecycles())
    names = {lc.name for lc in items}
    assert {"default", "research"} <= names


def test_iter_lifecycles_deduplicates_by_precedence(projects) -> None:
    """If the same name exists in both user library and built-ins, user wins (only one entry)."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "default.toml").write_text(
        """
name = "default"
description = "Custom default."
initial = "x"
terminal = ["y"]
[states.x]
[states.y]
[transitions]
x = ["y"]
""".strip()
    )
    items = [lc for lc in iter_lifecycles() if lc.name == "default"]
    assert len(items) == 1
    assert items[0].description == "Custom default."


def test_load_filename_must_match_name(projects) -> None:
    """A user-library TOML whose `name` field disagrees with its filename is rejected."""
    lib = projects / ".keel" / "lifecycles"
    lib.mkdir(parents=True)
    (lib / "research.toml").write_text(
        """
name = "different-name"
initial = "a"
terminal = ["b"]
[states.a]
[states.b]
[transitions]
a = ["b"]
""".strip()
    )
    with pytest.raises(LifecycleNotFoundError):
        load_lifecycle("research")
