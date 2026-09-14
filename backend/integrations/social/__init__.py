"""Adapter registry — the one place the pipeline looks up a platform.

Mirrors the lookup style already used by `modules/auth/providers`, so the
codebase has one idiom for "give me the thing that handles this platform".

Stage 1 registers the TikTok adapter here. Until then the registry is
empty on purpose: the interface is frozen, the implementations are not.
"""

from core.platforms import Platform

from .base import SocialPlatformAdapter

REGISTRY: dict[Platform, SocialPlatformAdapter] = {}


def get_adapter(platform: Platform) -> SocialPlatformAdapter:
    adapter = REGISTRY.get(platform)
    if adapter is None:
        known = ", ".join(p.value for p in REGISTRY) or "none registered yet"
        raise KeyError(f"No adapter for platform '{platform.value}'. Available: {known}")
    return adapter
