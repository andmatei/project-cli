"""Ticketing plugin protocol — keel core ships only the protocol + a mock provider."""
from __future__ import annotations

from typing import TYPE_CHECKING

from keel.ticketing.registry import load_provider, list_providers

if TYPE_CHECKING:
    from keel.manifest import ProjectManifest
    from keel.ticketing.base import TicketProvider


def get_provider_for_project(manifest: ProjectManifest) -> TicketProvider | None:
    """Read `[extensions.ticketing]` from a project manifest, instantiate the provider, configure it.

    Returns None if no ticketing config or the named provider plugin isn't installed.
    """
    cfg = manifest.extensions.get("ticketing")
    if not isinstance(cfg, dict):
        return None
    name = cfg.get("provider")
    if not isinstance(name, str) or not name:
        return None
    provider = load_provider(name)
    if provider is None:
        return None
    provider_cfg = cfg.get(name, {})
    if not isinstance(provider_cfg, dict):
        provider_cfg = {}
    provider.configure(provider_cfg)
    return provider


__all__ = ["get_provider_for_project", "list_providers", "load_provider"]
