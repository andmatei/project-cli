"""Tests for the shipped default lifecycle TOML."""

import tomllib
from importlib import resources

from keel.lifecycles.models import Lifecycle


def test_default_toml_shipped_in_wheel() -> None:
    """`keel.lifecycles.defaults.default.toml` is reachable via importlib.resources."""
    text = resources.files("keel.lifecycles.defaults").joinpath("default.toml").read_text()
    assert "name" in text
    assert "scoping" in text


def test_default_toml_parses_into_valid_lifecycle() -> None:
    raw = tomllib.loads(
        resources.files("keel.lifecycles.defaults").joinpath("default.toml").read_text()
    )
    lc = Lifecycle.model_validate(raw)
    assert lc.name == "default"
    assert lc.initial == "scoping"
    assert "scoping" in lc.states
    assert "designing" in lc.states
    assert "poc" in lc.states
    assert "implementing" in lc.states
    assert "shipping" in lc.states
    assert "done" in lc.states


def test_default_toml_transitions_match_legacy() -> None:
    raw = tomllib.loads(
        resources.files("keel.lifecycles.defaults").joinpath("default.toml").read_text()
    )
    lc = Lifecycle.model_validate(raw)
    # Linear walk: scoping -> designing -> poc -> implementing -> shipping -> done
    assert lc.transitions["scoping"] == ["designing"]
    assert lc.transitions["designing"] == ["poc"]
    assert lc.transitions["poc"] == ["implementing"]
    assert lc.transitions["implementing"] == ["shipping"]
    assert lc.transitions["shipping"] == ["done"]
