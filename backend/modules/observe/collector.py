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
import threading
import time
from collections import deque
from dataclasses import dataclass, field

MAX_LOGS = 5000
WINDOW_MINUTES = 60
MAX_LATENCY_SAMPLES_PER_MINUTE = 400
DB_HISTORY = 240

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


def record_request(method: str, path: str, status: int, duration_ms: float, client: str | None) -> None:
    """Called by the ASGI middleware once per finished request."""
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
            if record.exc_info and record.exc_info[1] is not None:
                message += f"\n{type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
            _append({
                "ts": int(record.created * 1000),
                "level": level,
                "source": record.name,
                "message": message[:4000],
            })
        except Exception:  # noqa: BLE001 — logging must never raise
            pass


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
    }
