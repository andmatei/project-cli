"""Ticketing plugin protocol — keel core ships only the protocol + a mock provider."""
from __future__ import annotations

from typing import TYPE_CHECKING

from keel.ticketing.registry import list_providers, load_provider

if TYPE_CHECKING:
    from keel.manifest import ProjectManifest
    from keel.output import Output
    from keel.ticketing.base import TicketProvider
    from keel.workspace import Scope


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


def with_provider(scope: Scope, *, no_push: bool) -> TicketProvider | None:
    """Resolve the project's configured ticketing provider, or None.

    Returns None if --no-push was passed, no ticketing config, or plugin not installed.
    """
    if no_push:
        return None
    from keel.manifest import load_project_manifest
    from keel.workspace import manifest_path
    proj_manifest = load_project_manifest(manifest_path(scope.project))
    return get_provider_for_project(proj_manifest)


def safe_push(out: Output, op_label: str, fn) -> None:
    """Call fn() and swallow exceptions as warnings.

    `op_label` is a short label like "create_milestone" used in the warning message.
    """
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        out.info(f"[warning] ticket {op_label} failed: {e}")


__all__ = ["get_provider_for_project", "with_provider", "safe_push", "list_providers", "load_provider"]
