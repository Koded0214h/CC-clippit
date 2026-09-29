"""In-memory counters for outbound deliveries (email today), read by the
ops screens. Process-local and reset on restart, like the rest of /observe."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_recent: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))


def record(channel: str, ok: bool, duration_ms: float, error: str | None = None) -> None:
    with _lock:
        _recent[channel].append({"ts": int(time.time() * 1000), "ok": ok, "ms": round(duration_ms, 1), "error": error})


def summary(channel: str, window_seconds: int = 3600) -> dict:
    cutoff = (time.time() - window_seconds) * 1000
    with _lock:
        rows = [r for r in _recent[channel] if r["ts"] >= cutoff]
    ok = [r for r in rows if r["ok"]]
    ms = sorted(r["ms"] for r in ok)
    return {
        "attempts": len(rows), "failed": len(rows) - len(ok),
        "success_rate": round(100 * len(ok) / len(rows), 2) if rows else None,
        "p50_ms": ms[len(ms) // 2] if ms else None,
        "errors": [r for r in reversed(rows) if not r["ok"]][:10],
    }


def buckets(channel: str, minutes: int = 60) -> list[dict]:
    now_min = int(time.time() // 60)
    out = {m: {"t": m * 60000, "ok": 0, "err": 0} for m in range(now_min - minutes + 1, now_min + 1)}
    with _lock:
        rows = list(_recent[channel])
    for r in rows:
        b = out.get(r["ts"] // 60000)
        if b:
            b["ok" if r["ok"] else "err"] += 1
    return list(out.values())
