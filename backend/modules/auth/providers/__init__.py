from . import facebook, instagram, threads, tiktok, x

REGISTRY = {
    tiktok.PLATFORM: tiktok,
    facebook.PLATFORM: facebook,
    instagram.PLATFORM: instagram,
    threads.PLATFORM: threads,
    x.PLATFORM: x,
}


def get_provider(name: str):
    provider = REGISTRY.get(name)
    if provider is None:
        raise KeyError(f"Unknown platform '{name}'. Known: {', '.join(REGISTRY)}")
    return provider
