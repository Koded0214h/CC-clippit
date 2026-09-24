from . import facebook, instagram, threads, tiktok, x, youtube

REGISTRY = {
    tiktok.PLATFORM: tiktok,
    facebook.PLATFORM: facebook,
    instagram.PLATFORM: instagram,
    threads.PLATFORM: threads,
    x.PLATFORM: x,
    youtube.PLATFORM: youtube,
}


def get_provider(name: str):
    provider = REGISTRY.get(name)
    if provider is None:
        raise KeyError(f"Unknown platform '{name}'. Known: {', '.join(REGISTRY)}")
    return provider
