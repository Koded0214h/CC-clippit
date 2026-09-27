from core.config import get_settings
from core.platforms import is_v1_platform

from . import facebook, instagram, threads, tiktok, x, youtube

REGISTRY = {
    tiktok.PLATFORM: tiktok,
    facebook.PLATFORM: facebook,
    instagram.PLATFORM: instagram,
    threads.PLATFORM: threads,
    x.PLATFORM: x,
    youtube.PLATFORM: youtube,
}

#: Settings attributes each provider's OAuth app needs — (client id, secret).
_CREDENTIALS = {
    "tiktok": ("tiktok_client_key", "tiktok_client_secret"),
    "facebook": ("facebook_app_id", "facebook_app_secret"),
    "instagram": ("instagram_app_id", "instagram_app_secret"),
    "threads": ("threads_app_id", "threads_app_secret"),
    "x": ("x_client_id", "x_client_secret"),
    "youtube": ("youtube_client_id", "youtube_client_secret"),
}


def get_provider(name: str):
    provider = REGISTRY.get(name)
    if provider is None:
        raise KeyError(f"Unknown platform '{name}'. Known: {', '.join(REGISTRY)}")
    return provider


def is_configured(name: str) -> bool:
    """Both halves of the platform's OAuth app credentials are set."""
    fields = _CREDENTIALS.get(name)
    if fields is None:
        return False
    settings = get_settings()
    return all(getattr(settings, field, "") for field in fields)


def is_connectable(name: str) -> bool:
    """A creator can start a connection today: a V1 platform (PRD) with a
    built provider and credentials set. Without credentials the platform
    would get an empty client id and show its own error page."""
    return name in REGISTRY and is_v1_platform(name) and is_configured(name)
