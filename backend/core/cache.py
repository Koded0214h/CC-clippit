"""A tiny in-process TTL cache.

`functools.lru_cache` doesn't fit here: it never expires, so it can't cache
a DB row that might change (a user's role, say) without going stale forever.
This is deliberately minimal — one process's memory, no eviction beyond TTL
and a max size. Fine for now; the moment this runs as more than one worker
or needs to be invalidated from another process, this needs to become a
real cache (Redis) instead.
"""

import time
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, ttl_seconds: float, max_size: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._store: dict[K, tuple[float, V]] = {}

    def get(self, key: K) -> V | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: K, value: V) -> None:
        if len(self._store) >= self.max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            self._store.pop(oldest_key, None)
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def invalidate(self, key: K) -> None:
        self._store.pop(key, None)
