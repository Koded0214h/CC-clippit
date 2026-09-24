"""Adapter registry — the one place the pipeline looks up a platform.

Mirrors the lookup style already used by `modules/auth/providers`, so the
codebase has one idiom for "give me the thing that handles this platform".

Adapters are registered as instances, one per platform, reused for the
life of the process — they hold configuration, never per-request state.
"""

from core.platforms import Platform

from .base import SocialPlatformAdapter
from .facebook import FacebookAdapter
from .instagram import InstagramAdapter
from .threads import ThreadsAdapter
from .tiktok import TikTokAdapter
from .x import XAdapter
from .youtube import YouTubeAdapter

REGISTRY: dict[Platform, SocialPlatformAdapter] = {
    Platform.tiktok: TikTokAdapter(),
    Platform.instagram: InstagramAdapter(),
    Platform.facebook: FacebookAdapter(),
    Platform.threads: ThreadsAdapter(),
    Platform.x: XAdapter(),
    Platform.youtube: YouTubeAdapter(),
}


def get_adapter(platform: Platform) -> SocialPlatformAdapter:
    adapter = REGISTRY.get(platform)
    if adapter is None:
        known = ", ".join(p.value for p in REGISTRY) or "none registered yet"
        raise KeyError(f"No adapter for platform '{platform.value}'. Available: {known}")
    return adapter
