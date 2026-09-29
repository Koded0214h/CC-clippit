# Ops API — System health & Trust and delivery

Everything the admin screens **System health**, **Webhooks**, **Social providers** and
**Notifications** need. Same payloads over REST (first paint) and a WebSocket (live).
Operator login required (`role = admin`); a non-admin gets 403.

Numbers come from live measurement, never fixtures. Two honest limits:

* Webhook, email and traffic figures are counted **since the API process last started**
  (nothing persists webhook attempts). Each feed says so in `scope`.
* `availability_30d` is persisted (table `ops_health_samples`, one sample per service per minute)
  so it survives deploys. It is `null` until ~5 minutes of history exist. A restart, outage or
  database slower than 2 s counts against it. Only `api` and `database` are sampled; other
  services return `null`.

## REST

| Endpoint | Screen | Topic |
|---|---|---|
| `GET /admin/system/health` | System health | `system` |
| `GET /admin/delivery/webhooks` | Webhooks | `webhooks` |
| `GET /admin/delivery/social` | Social providers | `social` |
| `GET /admin/delivery/notifications` | Notifications | `notifications` |
| `GET /admin/ops/snapshot` | all four in one call | — |

Send the usual `Authorization: Bearer <access token>`.

## WebSocket — `wss://api.clippit.click/admin/ws`

Browsers can't set headers on a WebSocket and a token in the URL would be logged, so
**authenticate with the first message**:

```jsonc
// client → server, within 5 s of connecting
{ "type": "auth", "token": "<access token>" }
// server → client
{ "type": "ready", "topics": ["notifications","social","system","webhooks"], "snapshot_seconds": 10 }
```

Close codes: `4401` bad/missing token or no auth message, `4403` not an admin. Don't retry either.

After `ready` you receive **every topic** (snapshot immediately, then every 10 s). Narrow it:

```jsonc
{ "type": "subscribe", "topics": ["webhooks"] }      // → { "type": "subscribed", "topics": ["webhooks"] } + fresh snapshots
{ "type": "ping" }                                    // → { "type": "pong" }   (send every ~25 s to keep proxies open)
```

Server messages:

```jsonc
{ "type": "snapshot", "topic": "system", "data": { /* same as the REST response */ } }
{ "type": "event", "topic": "webhooks", "event": {     // pushed the moment a webhook hits the API
    "ts": 1780000000000, "path": "/webhooks/payments", "status": 401, "duration_ms": 3.1,
    "provider": "payments", "title": "Rejected", "result": "rejected" } }   // complete | rejected | failed
{ "type": "error", "topic": "social", "message": "could not build this topic" }  // stream continues
```

A ready-made client with reconnect/backoff lives in `frontend/lib/api/opsSocket.ts`
(`openOpsSocket`), and `AdminOps.tsx` shows the pattern: REST first, socket updates, poll REST
if the socket is unauthorized.

## Payloads

### System — `GET /admin/system/health`

```jsonc
{
  "generated_at": 1780000000000, "environment": "production",
  "status": "operational",                 // operational | degraded | down  (worst service)
  "uptime_seconds": 86400, "started_at": 1779913600000,
  "services": [
    { "key": "api",          "name": "API gateway",     "status": "operational",
      "headline": { "label": "Latency (p95)", "display": "48 ms" },
      "detail": "1204 requests · 0.1% 5xx (30 min)",
      "availability_30d": 99.99, "trend": [41, 44, 48, ...] },
    { "key": "database",     "name": "Database",        "headline": { "label": "Latency", "display": "12 ms" }, ... },
    { "key": "jobs",         "name": "Queue workers",   "headline": { "label": "Current work", "display": "6 jobs" },
      "jobs": [{ "name": "settle", "interval_seconds": 300, "runs": 12, "failures": 0,
                 "last_run_at": 1780000000000, "last_ok": true, "last_error": null, "last_duration_ms": 41.2 }] },
    { "key": "media_checks", "name": "Media checks",    "headline": { "label": "Current work", "display": "43 open" },
      "checking": 38, "needs_review": 5 },
    { "key": "storage",      "name": "Object storage",  "headline": { "label": "Backend", "display": "cloudinary" } },  // config only, not probed
    { "key": "host",         "name": "Host resources",  "headline": { "label": "CPU · RAM", "display": "CPU 8% · RAM 68%" },
      "resources": { "proc_cpu": 1.2, "proc_rss_mb": 101, "sys_cpu": 8.8, "sys_mem_pct": 68.6, "load1": 1.9, "cores": 16, "loop_lag_ms": 1.1 } }
  ],
  "requests": 1204, "error_rate": 0.1, "throughput_rpm": 40.1,
  "latency": { "p50": 12, "p95": 48, "p99": 90 },
  "series": [{ "t": 1780000000000, "ok": 40, "client_err": 2, "server_err": 0, "p50": 12, "p95": 48 }],   // 30 × 1-minute
  "db_history": [{ "ts": 1780000000000, "ok": true, "ms": 12 }], "log_counts": { "info": 900, "warn": 12, "error": 1 }
}
```

`status` per service: `operational | degraded | down | sandbox` (dev backend) `| disabled`
(e.g. background jobs switched off). There is no "Receipt renderer" service: receipts are rendered
inline, so there is no queue to report.

### Delivery feeds — webhooks / social / notifications

All three share one shape:

```jsonc
{
  "kind": "webhooks", "generated_at": 1780000000000,
  "status": "healthy",                      // healthy | attention | failing   (worst card)
  "scope": "Counted since the API last restarted",
  "cards": [{
    "key": "payments", "name": "Payments provider", "note": "Funding and transfer events",
    "status": "healthy",                    // healthy | attention | failing | quiet | unconfigured
    "success_rate": 99.94,                  // 0-100, null when nothing to measure
    "headline": { "label": "p95 latency", "display": "82 ms" },
    "window": { "minutes": 60, "buckets": [{ "t": 1780000000000, "ok": 3, "retried": 0, "failed": 0 }] },  // null if no time series
    "events": [{ "id": "WEBHOOKS-88410", "ts": 1780000000000, "title": "Event accepted", "ref": "/webhooks/payments", "result": "complete" }],
    "facts": { "events": 41, "rejected": 0, "failed": 0 }
  }]
}
```

| Feed | Cards (`key`) | `success_rate` means | `window` / `events` |
|---|---|---|---|
| webhooks | `payments`, `social` | non-4xx/5xx share of deliveries | per-minute buckets + last 15 deliveries |
| social | one per platform (`tiktok`, `instagram`, …) | tracked posts **not** failing their last read | none; `facts` has `connected, expired_tokens, tracked_posts, delayed_checks, failing_checks, last_success_at` |
| notifications | `email`, `in_app`, `push` | email sends that succeeded | email: per-minute buckets + recent failures; in_app: counts by kind |

Status rules — webhooks: `quiet` no traffic, `attention` any 4xx (e.g. bad signature), `failing` any 5xx.
Social: `unconfigured` no client credentials, `attention` delayed reads (next poll >10 min late), expired
tokens or failing reads, `failing` every tracked post failing. Email: `quiet` no sends, `attention` any failure,
`failing` <50% success.

There is no SMS or "identity provider" webhook card: neither exists in the backend yet. `retried` is always
`0` today: we don't observe provider retries.
