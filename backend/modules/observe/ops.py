"""The ops-screen contract, shared by the REST endpoints and the WebSocket.

Every builder returns plain JSON-able dicts; `docs: architecture/ops-api.md`
documents the shapes for the frontend. Nothing here writes anything.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core import delivery_stats
from core.config import get_settings
from core.jobs import status as job_status

from . import availability, collector, resources
from .router import _probe_db

TOPICS = ("system", "webhooks", "social", "notifications")


def _overall(cards: list[dict]) -> str:
    statuses = {c["status"] for c in cards}
    return "failing" if "failing" in statuses else "attention" if "attention" in statuses else "healthy"


def _ms(v: float | None) -> str:
    return "—" if v is None else (f"{v / 1000:.1f} s" if v >= 1000 else f"{round(v)} ms")


# --- system --------------------------------------------------------------------

async def system(db: AsyncSession) -> dict:
    from modules.submissions.models import Submission, VerificationStatus

    s = get_settings()
    dbp = await _probe_db()
    snap = collector.snapshot(30)
    res = resources.latest()
    avail = await availability.availability_30d(db)
    p95 = snap["latency"]["p95"]

    jobs = job_status()
    failing_jobs = [j for j in jobs if j["last_ok"] is False]
    counts = dict((getattr(k, "value", k), n) for k, n in (await db.execute(
        select(Submission.verification_status, func.count())
        .where(Submission.verification_status.in_([VerificationStatus.checking, VerificationStatus.needs_review]))
        .group_by(Submission.verification_status)
    )).all())
    checking, review = counts.get("checking", 0), counts.get("needs_review", 0)

    def svc(key, name, status, label, display, detail, availability_30d=None, trend=None, **extra):
        return {"key": key, "name": name, "status": status, "headline": {"label": label, "display": display},
                "metric": display, "detail": detail, "availability_30d": availability_30d, "trend": trend or [], **extra}

    services = [
        svc("api", "API gateway", "operational" if snap["error_rate"] < 5 else "degraded", "Latency (p95)", _ms(p95),
            f"{snap['requests']} requests · {snap['error_rate']}% 5xx (30 min)", avail["api"],
            [r["p95"] for r in snap["series"] if r["p95"] is not None][-18:]),
        svc("database", "Database", "operational" if dbp["ok"] else "down", "Latency", _ms(dbp["ms"]) if dbp["ok"] else (dbp["error"] or "unreachable"),
            "SELECT 1 round trip", avail["database"], [p["ms"] for p in snap["db_history"] if p["ms"] is not None][-18:]),
        svc("jobs", "Queue workers", "disabled" if not s.background_jobs_enabled else "degraded" if failing_jobs else "operational",
            "Current work", f"{len(jobs)} jobs",
            ("background jobs are switched off (BACKGROUND_JOBS_ENABLED)" if not s.background_jobs_enabled
             else f"{len(failing_jobs)} failing: " + ", ".join(j["name"] for j in failing_jobs) if failing_jobs else "every job's last run succeeded"),
            jobs=jobs),
        svc("media_checks", "Media checks", "operational", "Current work", f"{checking + review} open",
            f"{checking} checking · {review} awaiting a human decision", checking=checking, needs_review=review),
        svc("storage", "Object storage", "sandbox" if s.storage_backend == "local" else "operational", "Backend", s.storage_backend, "media backend (configuration only; not probed)"),
        svc("host", "Host resources", "degraded" if res["sys_mem_pct"] >= 90 or res["sys_cpu"] >= 90 else "operational", "CPU · RAM",
            f"CPU {res['sys_cpu']}% · RAM {res['sys_mem_pct']}%",
            f"API uses {res['proc_rss_mb']} MB, {res['proc_cpu']}% of a core · loop lag {res['loop_lag_ms']} ms", resources=res),
    ]
    order = {"down": 3, "degraded": 2}
    worst = max(services, key=lambda x: order.get(x["status"], 0))["status"]
    return {
        "generated_at": int(time.time() * 1000), "environment": s.environment,
        "status": worst if worst in order else "operational",
        "uptime_seconds": snap["uptime_seconds"], "started_at": snap["started_at"],
        "services": services,
        "requests": snap["requests"], "error_rate": snap["error_rate"], "throughput_rpm": snap["throughput_rpm"],
        "latency": snap["latency"], "series": snap["series"], "db_history": snap["db_history"], "log_counts": snap["log_counts"],
    }


# --- delivery feeds (webhooks / social / notifications) ----------------------------

def _feed(kind: str, scope: str, cards: list[dict]) -> dict:
    return {"kind": kind, "generated_at": int(time.time() * 1000), "status": _overall(cards), "scope": scope, "cards": cards}


def _card(key, name, note, status, success_rate, label, display, window=None, events=None, facts=None) -> dict:
    return {"key": key, "name": name, "note": note, "status": status, "success_rate": success_rate,
            "headline": {"label": label, "display": display}, "window": window, "events": events or [], "facts": facts or {}}


def webhooks() -> dict:
    cards = []
    for key, name, note, prefix in (
        ("payments", "Payments provider", "Funding and transfer events", "/webhooks/payments"),
        ("social", "Social platforms", "Deauthorize and data-deletion callbacks", "/webhooks/social"),
    ):
        routes = collector.routes_with_prefix(prefix)
        n = sum(r["count"] for r in routes)
        rejected = sum(r["client_err"] for r in routes)
        failed = sum(r["server_err"] for r in routes)
        p95 = max((r["p95_ms"] or 0 for r in routes), default=0) or None
        status = "quiet" if n == 0 else "failing" if failed else "attention" if rejected else "healthy"
        events = [
            {"id": f"WEBHOOKS-{e['id']}", "ts": e["ts"], "title": collector.webhook_event(e["path"], e["status"], e["duration_ms"], e["ts"])["title"],
             "ref": e["path"], "result": collector.webhook_event(e["path"], e["status"], e["duration_ms"], e["ts"])["result"]}
            for e in collector.recent_requests(prefix, 15)
        ]
        cards.append(_card(key, name, note, status, None if n == 0 else round(100 * (n - rejected - failed) / n, 2), "p95 latency", _ms(p95),
                           {"minutes": 60, "buckets": collector.bucketize(prefix, 60)}, events,
                           {"events": n, "rejected": rejected, "failed": failed}))
    return _feed("webhooks", "Counted since the API last restarted", cards)


async def social(db: AsyncSession) -> dict:
    from modules.auth.models import SocialAccount
    from modules.auth.providers import REGISTRY
    from modules.intelligence.models import ContentTracking, SocialContent
    from modules.intelligence.scheduling import TrackingStatus

    s = get_settings()
    now = datetime.now(timezone.utc)
    accounts = {str(getattr(r[0], "value", r[0])): r for r in (await db.execute(
        select(SocialAccount.platform, func.count(),
               func.count().filter(SocialAccount.expires_at.is_not(None), SocialAccount.expires_at < now, SocialAccount.refresh_token.is_(None)))
        .group_by(SocialAccount.platform))).all()}
    tracking = {str(getattr(r[0], "value", r[0])): r for r in (await db.execute(
        select(SocialContent.platform, func.count(),
               func.count().filter(ContentTracking.next_poll_at < now - timedelta(minutes=10)),
               func.count().filter(ContentTracking.consecutive_failures > 0),
               func.max(ContentTracking.last_success_at))
        .join(ContentTracking, ContentTracking.content_id == SocialContent.id)
        .where(ContentTracking.status == TrackingStatus.active).group_by(SocialContent.platform))).all()}
    cards = []
    for platform in REGISTRY:
        creds = getattr(s, f"{platform}_client_key", None) or getattr(s, f"{platform}_app_id", None) or getattr(s, f"{platform}_client_id", None)
        connected, expired = (accounts[platform][1], accounts[platform][2]) if platform in accounts else (0, 0)
        tracked, delayed, failing, last_ok = (tracking[platform][1:5] if platform in tracking else (0, 0, 0, None))
        status = "unconfigured" if not creds else "failing" if tracked and failing == tracked else "attention" if (delayed or expired or failing) else "healthy"
        note = ("No credentials configured" if not creds else f"{delayed} checks delayed" if delayed else f"{expired} tokens expired" if expired else "Readings current")
        cards.append(_card(platform, platform.capitalize(), note, status, None if not tracked else round(100 * (tracked - failing) / tracked, 2),
                           "Connected", str(connected), None, [],
                           {"configured": bool(creds), "connected": connected, "expired_tokens": expired, "tracked_posts": tracked,
                            "delayed_checks": delayed, "failing_checks": failing, "last_success_at": last_ok.isoformat() if last_ok else None}))
    return _feed("social", "Live from the database", cards)


async def notifications(db: AsyncSession) -> dict:
    from modules.notifications.models import Notification, PushSubscription

    s = get_settings()
    em = delivery_stats.summary("email")
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    created, unread = (await db.execute(select(func.count(), func.count().filter(Notification.read_at.is_(None))).where(Notification.created_at >= since))).one()
    by_kind = (await db.execute(select(Notification.kind, func.count()).where(Notification.created_at >= since).group_by(Notification.kind).order_by(func.count().desc()).limit(6))).all()
    push = await db.scalar(select(func.count()).select_from(PushSubscription)) or 0
    rate = em["success_rate"]
    email_status = "quiet" if not em["attempts"] else "failing" if rate is not None and rate < 50 else "attention" if em["failed"] else "healthy"
    cards = [
        _card("email", "Email", f"Backend: {s.email_backend}", email_status, rate, "Median send", _ms(em["p50_ms"]),
              {"minutes": 60, "buckets": [{"t": b["t"], "ok": b["ok"], "retried": 0, "failed": b["err"]} for b in delivery_stats.buckets("email", 60)]},
              [{"id": f"EMAIL-{e['ts']}", "ts": e["ts"], "title": "Send failed", "ref": e["error"] or "error", "result": "failed"} for e in em["errors"]],
              {"attempts": em["attempts"], "failed": em["failed"]}),
        _card("in_app", "In-app", f"{unread} unread of {created} (24 h)", "healthy", None, "Created (24 h)", str(created), None,
              [{"id": f"KIND-{k}", "ts": None, "title": k, "ref": "last 24 h", "result": str(n)} for k, n in by_kind],
              {"created_24h": created, "unread_24h": unread}),
        _card("push", "Push", "Browser subscriptions", "healthy" if push else "quiet", None, "Subscriptions", str(push), None, [], {"subscriptions": push}),
    ]
    return _feed("notifications", "Email counted since the API last restarted", cards)


async def build(topic: str, db: AsyncSession) -> dict:
    if topic == "system":
        return await system(db)
    if topic == "webhooks":
        return webhooks()
    if topic == "social":
        return await social(db)
    if topic == "notifications":
        return await notifications(db)
    raise KeyError(topic)
