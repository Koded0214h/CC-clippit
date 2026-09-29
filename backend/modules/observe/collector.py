"""In-process telemetry for the /observe dashboard.

Everything lives in memory and dies with the process: this is a "what is the
API doing right now" view, not a metrics store. One uvicorn worker (see
deploy/clippit-api.service) is what makes in-process counters accurate; with
more workers each would keep its own numbers.

Nothing here ever raises into the request path: a telemetry bug must not
take an API call down with it.
"""

from __future__ import annotations

import itertools
import logging
import traceback
import threading
import time
from collections import deque
from dataclasses import dataclass, field

MAX_LOGS = 5000
WINDOW_MINUTES = 60
MAX_LATENCY_SAMPLES_PER_MINUTE = 400
DB_HISTORY = 240
MAX_TRACEBACK_CHARS = 8000

# Upper bounds (ms) of the latency bands shown in the pie chart.
LATENCY_BANDS = (100, 300, 1000)
LATENCY_BAND_LABELS = ("< 100 ms", "100–300 ms", "0.3–1 s", "> 1 s")

_started_at = time.time()
_ids = itertools.count(1)
_lock = threading.Lock()
_logs: deque[dict] = deque(maxlen=MAX_LOGS)


@dataclass
class _Minute:
    ok: int = 0          # 1xx-3xx
    client_err: int = 0  # 4xx
    server_err: int = 0  # 5xx
    bands: list[int] = field(default_factory=lambda: [0] * (len(LATENCY_BANDS) + 1))
    samples: list[float] = field(default_factory=list)
    seen: int = 0

    @property
    def total(self) -> int:
        return self.ok + self.client_err + self.server_err


_minutes: dict[int, _Minute] = {}
MAX_ROUTES = 300


@dataclass
class _Route:
    """Lifetime totals for one "METHOD /route/{template}" (since process start)."""

    count: int = 0
    client_err: int = 0
    server_err: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    last_ts: int = 0
    last_status: int = 0
    samples: list[float] = field(default_factory=list)


_routes: dict[str, _Route] = {}
db_history: deque[dict] = deque(maxlen=DB_HISTORY)


def _level_for_status(status: int) -> str:
    if status >= 500:
        return "error"
    if status >= 400:
        return "warn"
    return "info"


def _append(entry: dict) -> None:
    with _lock:
        entry["id"] = next(_ids)
        _logs.append(entry)


def record_request(method: str, path: str, status: int, duration_ms: float, client: str | None, detail: dict | None = None) -> None:
    """Called by the ASGI middleware once per finished request. `detail` (raw path,
    exception, response excerpt…) rides along for the overlay and is only kept
    for 4xx/5xx so healthy traffic stays cheap."""
    now = time.time()
    minute = int(now // 60)
    with _lock:
        bucket = _minutes.get(minute)
        if bucket is None:
            bucket = _minutes[minute] = _Minute()
            for old in [m for m in _minutes if m <= minute - WINDOW_MINUTES]:
                del _minutes[old]
        if status >= 500:
            bucket.server_err += 1
        elif status >= 400:
            bucket.client_err += 1
        else:
            bucket.ok += 1
        band = sum(duration_ms >= edge for edge in LATENCY_BANDS)
        bucket.bands[band] += 1
        # Reservoir sampling keeps percentiles honest without unbounded memory.
        bucket.seen += 1
        if len(bucket.samples) < MAX_LATENCY_SAMPLES_PER_MINUTE:
            bucket.samples.append(duration_ms)
        else:
            slot = int(now * 1000003) % bucket.seen
            if slot < MAX_LATENCY_SAMPLES_PER_MINUTE:
                bucket.samples[slot] = duration_ms
    with _lock:
        key = f"{method} {path}"
        route = _routes.get(key)
        if route is None and len(_routes) < MAX_ROUTES:  # bounded: unknown paths (scanners) can't grow this
            route = _routes[key] = _Route()
        if route is not None:
            route.count += 1
            route.client_err += 400 <= status < 500
            route.server_err += status >= 500
            route.total_ms += duration_ms
            route.max_ms = max(route.max_ms, duration_ms)
            route.last_ts, route.last_status = int(now * 1000), status
            route.samples.append(duration_ms)
            if len(route.samples) > 200:
                del route.samples[:100]
    if path.startswith("/webhooks"):
        _publish({"type": "event", "topic": "webhooks", "event": webhook_event(path, status, duration_ms, int(now * 1000))})
    _append({
        "ts": int(now * 1000),
        "level": _level_for_status(status),
        "source": "http",
        "message": f"{method} {path} → {status}",
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "client": client,
        **({"detail": detail} if detail and status >= 400 else {}),
    })


def record_db_probe(ok: bool, latency_ms: float | None, error: str | None = None) -> None:
    with _lock:
        db_history.append({"ts": int(time.time() * 1000), "ok": ok, "ms": None if latency_ms is None else round(latency_ms, 1), "error": error})


class LogHandler(logging.Handler):
    """Mirrors application log records into the same buffer as requests."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = {"CRITICAL": "error", "ERROR": "error", "WARNING": "warn"}.get(record.levelname, "info")
            message = record.getMessage()
            entry = {
                "ts": int(record.created * 1000),
                "level": level,
                "source": record.name,
                "message": message[:4000],
            }
            if record.exc_info and record.exc_info[1] is not None:
                exc = record.exc_info[1]
                entry["message"] = f"{message}\n{type(exc).__name__}: {exc}"[:4000]
                entry["detail"] = {"exception": describe_exception(exc)}
            _append(entry)
        except Exception:  # noqa: BLE001 — logging must never raise
            pass


def describe_exception(exc: BaseException) -> dict:
    """Type, message and a capped traceback (walks __cause__/__context__ like Python does)."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if len(tb) > MAX_TRACEBACK_CHARS:  # keep the tail: the raising frame is what matters
        tb = "… (truncated)\n" + tb[-MAX_TRACEBACK_CHARS:]
    return {"type": type(exc).__name__, "message": str(exc)[:1000], "traceback": tb}


_installed = False


def install_log_capture() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    handler = LogHandler(level=logging.INFO)
    app_logger = logging.getLogger("clippit")
    app_logger.setLevel(logging.INFO)
    if not logging.getLogger().handlers:
        # Adding a handler here stops Python's "last resort" stderr output for
        # this logger's warnings, so keep them going to journald ourselves.
        stderr = logging.StreamHandler()
        stderr.setLevel(logging.WARNING)
        app_logger.addHandler(stderr)
    app_logger.addHandler(handler)
    logging.getLogger("uvicorn.error").addHandler(handler)


def logs_since(after: int = 0, limit: int = 500) -> list[dict]:
    with _lock:
        rows = [e for e in _logs if e["id"] > after]
    return rows[-limit:]


def _percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, int(round(q * (len(sorted_values) - 1))))
    return round(sorted_values[idx], 1)


def snapshot(window_minutes: int = 30) -> dict:
    now_minute = int(time.time() // 60)
    window_minutes = max(5, min(window_minutes, WINDOW_MINUTES))
    series = []
    totals = _Minute()
    all_samples: list[float] = []
    with _lock:
        for minute in range(now_minute - window_minutes + 1, now_minute + 1):
            b = _minutes.get(minute)
            row = {"t": minute * 60 * 1000, "ok": 0, "client_err": 0, "server_err": 0, "p50": None, "p95": None}
            if b is not None:
                s = sorted(b.samples)
                row.update(ok=b.ok, client_err=b.client_err, server_err=b.server_err, p50=_percentile(s, 0.5), p95=_percentile(s, 0.95))
                totals.ok += b.ok
                totals.client_err += b.client_err
                totals.server_err += b.server_err
                totals.bands = [a + c for a, c in zip(totals.bands, b.bands)]
                all_samples.extend(b.samples)
            series.append(row)
        db = list(db_history)
    all_samples.sort()
    total = totals.total
    return {
        "started_at": int(_started_at * 1000),
        "uptime_seconds": int(time.time() - _started_at),
        "window_minutes": window_minutes,
        "requests": total,
        "error_rate": round(100 * totals.server_err / total, 2) if total else 0.0,
        "client_error_rate": round(100 * totals.client_err / total, 2) if total else 0.0,
        "throughput_rpm": round(total / window_minutes, 1),
        "throughput_rps": round(total / (window_minutes * 60), 2),
        "latency": {"p50": _percentile(all_samples, 0.5), "p95": _percentile(all_samples, 0.95), "p99": _percentile(all_samples, 0.99)},
        "latency_bands": {"labels": list(LATENCY_BAND_LABELS), "counts": totals.bands},
        "series": series,
        "db_history": db,
        "top_routes": top_routes(8, "count"),
        "slow_routes": top_routes(6, "slow"),
        "log_counts": log_counts(),
    }


def webhook_event(path: str, status: int, duration_ms: float, ts: int) -> dict:
    return {
        "ts": ts, "path": path, "status": status, "duration_ms": round(duration_ms, 1),
        "provider": "payments" if path.startswith("/webhooks/payments") else "social",
        "title": "Handler failed" if status >= 500 else "Rejected" if status >= 400 else "Event accepted",
        "result": "failed" if status >= 500 else "rejected" if status >= 400 else "complete",
    }


def _route_row(key: str, r: _Route) -> dict:
    method, path = key.split(" ", 1)
    s = sorted(r.samples)
    return {
        "method": method, "path": path, "count": r.count,
        "client_err": r.client_err, "server_err": r.server_err,
        "avg_ms": round(r.total_ms / r.count, 1), "p95_ms": _percentile(s, 0.95), "max_ms": round(r.max_ms, 1),
        "last_ts": r.last_ts, "last_status": r.last_status,
    }


def top_routes(limit: int = 8, by: str = "count") -> list[dict]:
    with _lock:
        rows = [_route_row(k, r) for k, r in _routes.items()]
    key = {"count": "count", "slow": "p95_ms", "errors": "server_err"}.get(by, "count")
    rows.sort(key=lambda row: row[key] or 0, reverse=True)
    return rows[:limit]


def routes_with_prefix(prefix: str) -> list[dict]:
    with _lock:
        return [_route_row(k, r) for k, r in _routes.items() if k.split(" ", 1)[1].startswith(prefix)]


def bucketize(prefix: str, minutes: int = 60) -> list[dict]:
    """Per-minute ok / failed request counts for paths under `prefix`, from the log buffer."""
    now_min = int(time.time() // 60)
    out = {m: {"t": m * 60000, "ok": 0, "retried": 0, "failed": 0} for m in range(now_min - minutes + 1, now_min + 1)}
    with _lock:
        rows = [e for e in _logs if e.get("source") == "http" and e["path"].startswith(prefix)]
    for e in rows:
        b = out.get(e["ts"] // 60000)
        if b:
            b["ok" if e["status"] < 400 else "failed"] += 1
    return list(out.values())


# --- live fan-out for the admin WebSocket ---------------------------------------
_subscribers: set = set()


def subscribe():
    import asyncio

    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    return q


def unsubscribe(q) -> None:
    _subscribers.discard(q)


def _publish(message: dict) -> None:
    for q in list(_subscribers):
        try:
            q.put_nowait(message)
        except Exception:  # noqa: BLE001 — a slow client drops events, never blocks a request
            pass


def recent_requests(prefix: str, limit: int = 30) -> list[dict]:
    with _lock:
        rows = [e for e in _logs if e.get("source") == "http" and e["path"].startswith(prefix)]
    return rows[-limit:][::-1]


def log_counts() -> dict:
    with _lock:
        counts = {"info": 0, "warn": 0, "error": 0}
        for e in _logs:
            counts[e["level"]] += 1
    return counts
