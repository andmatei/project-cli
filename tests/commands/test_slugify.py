"""Edge-case coverage for the slugifier used by `keel new`."""
import pytest
from keel.commands.new import _slugify


def test_slugify_lowercases_and_replaces_spaces() -> None:
    assert _slugify("Foo Bar") == "foo-bar"


def test_slugify_strips_specials() -> None:
    assert _slugify("foo!@#bar") == "foobar"


def test_slugify_empty_input() -> None:
    assert _slugify("") == ""


def test_slugify_whitespace_only() -> None:
    assert _slugify("   ") == ""


def test_slugify_all_specials() -> None:
    assert _slugify("!@#$%") == ""


def test_slugify_unicode_dropped() -> None:
    """Current behavior: non-ASCII characters are stripped silently."""
    assert _slugify("café") == "caf"


def test_slugify_leading_trailing_spaces_trimmed() -> None:
    assert _slugify("  hello  ") == "hello"


def test_slugify_keeps_existing_dashes() -> None:
    assert _slugify("a-b-c") == "a-b-c"
