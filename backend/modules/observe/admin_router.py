"""Read-only feeds for the admin app's "System health" and "Trust & delivery"
screens. Same in-process telemetry as /observe, but behind the normal admin
login instead of the dashboard password.

Webhook/delivery numbers are counted from live traffic since the API process
last started (nothing persists webhook attempts today), and every payload
says so via `since` so the UI never presents them as lifetime figures.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.jobs import registered as registered_jobs
from modules.admin.router import require_admin
from modules.auth.models import SocialAccount, User
from modules.notifications.models import Notification, PushSubscription

from . import collector
from .router import _probe_db

router = APIRouter(prefix="/admin", tags=["admin"])


def _ratio_ok(count: int, errors: int) -> float | None:
    return None if not count else round(100 * (count - errors) / count, 2)


@router.get("/system/health")
async def system_health(admin: User = Depends(require_admin)):
    s = get_settings()
    db = await _probe_db()
    snap = collector.snapshot(30)
    services = [
        {"name": "API", "status": "operational" if snap["error_rate"] < 5 else "degraded",
         "metric": f"p95 {snap['latency']['p95']} ms" if snap["latency"]["p95"] is not None else "no traffic yet",
         "detail": f"{snap['requests']} requests · {snap['error_rate']}% 5xx (30 min)"},
        {"name": "Database", "status": "operational" if db["ok"] else "down",
         "metric": f"{db['ms']} ms" if db["ok"] else (db["error"] or "unreachable"), "detail": "SELECT 1 round trip"},
        {"name": "Background jobs", "status": "operational" if s.background_jobs_enabled else "disabled",
         "metric": f"{len(registered_jobs())} registered", "detail": "settlement, reconcile and Intelligence polling run in the API process"},
        {"name": "Payments", "status": "sandbox" if s.payment_provider == "sandbox" else "operational",
         "metric": s.payment_provider, "detail": "provider configuration"},
        {"name": "Email", "status": "sandbox" if s.email_backend == "console" else "operational",
         "metric": s.email_backend, "detail": "sender backend"},
        {"name": "Storage", "status": "sandbox" if s.storage_backend == "local" else "operational",
         "metric": s.storage_backend, "detail": "media backend"},
    ]
    return {
        "environment": s.environment,
        "uptime_seconds": snap["uptime_seconds"],
        "started_at": snap["started_at"],
        "services": services,
        "requests": snap["requests"],
        "error_rate": snap["error_rate"],
        "throughput_rpm": snap["throughput_rpm"],
        "latency": snap["latency"],
        "series": snap["series"],
        "db_history": snap["db_history"],
        "log_counts": snap["log_counts"],
    }


def _traffic_group(label: str, prefix: str, note: str) -> dict:
    routes = collector.routes_with_prefix(prefix)
    count = sum(r["count"] for r in routes)
    rejected = sum(r["client_err"] for r in routes)   # 4xx: bad signature etc.
    failed = sum(r["server_err"] for r in routes)
    p95 = max((r["p95_ms"] or 0 for r in routes), default=0)
    return {
        "name": label, "note": note, "events": count, "rejected": rejected, "failed": failed,
        "success_rate": _ratio_ok(count, rejected + failed), "p95_ms": p95 or None,
        "last_ts": max((r["last_ts"] for r in routes), default=None),
    }


@router.get("/delivery/webhooks")
async def webhook_delivery(admin: User = Depends(require_admin)):
    groups = [
        _traffic_group("Payments provider", "/webhooks/payments", "Funding and transfer events"),
        _traffic_group("Social platforms", "/webhooks/social", "Deauthorize and data-deletion callbacks"),
    ]
    recent = [
        {"ts": e["ts"], "path": e["path"], "method": e["method"], "status": e["status"], "duration_ms": e["duration_ms"]}
        for e in collector.recent_requests("/webhooks", 30)
    ]
    snap = collector.snapshot(60)
    buckets = [{"t": r["t"], "ok": r["ok"], "err": r["client_err"] + r["server_err"]} for r in snap["series"]]
    return {"since": snap["started_at"], "groups": groups, "recent": recent, "buckets": buckets}


@router.get("/delivery/social")
async def social_delivery(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from modules.auth.providers import REGISTRY

    s = get_settings()
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(
            SocialAccount.platform,
            func.count(),
            func.count().filter(SocialAccount.expires_at.is_not(None), SocialAccount.expires_at < now, SocialAccount.refresh_token.is_(None)),
            func.max(SocialAccount.updated_at),
        ).group_by(SocialAccount.platform)
    )).all()
    stats = {r[0].value if hasattr(r[0], "value") else str(r[0]): r for r in rows}
    out = []
    for platform in REGISTRY:
        creds = (getattr(s, f"{platform}_client_key", None) or getattr(s, f"{platform}_app_id", None) or getattr(s, f"{platform}_client_id", None))
        r = stats.get(platform)
        connected, expired = (r[1], r[2]) if r else (0, 0)
        out.append({
            "name": platform, "configured": bool(creds), "connected": connected, "expired": expired,
            "last_update": r[3].isoformat() if r and r[3] else None,
            "status": "unconfigured" if not creds else "attention" if expired else "healthy",
        })
    return {"platforms": out}


@router.get("/delivery/notifications")
async def notification_delivery(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    s = get_settings()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    created, unread = (await db.execute(
        select(func.count(), func.count().filter(Notification.read_at.is_(None))).where(Notification.created_at >= since)
    )).one()
    by_kind = (await db.execute(
        select(Notification.kind, func.count()).where(Notification.created_at >= since)
        .group_by(Notification.kind).order_by(func.count().desc()).limit(6)
    )).all()
    push_subs = await db.scalar(select(func.count()).select_from(PushSubscription))
    email_problems = [
        {"ts": e["ts"], "message": e["message"][:200]}
        for e in collector.logs_since(0, 1000) if e["source"].startswith("clippit.email") and e["level"] != "info"
    ][-10:][::-1]
    return {
        "email": {"backend": s.email_backend, "problems": email_problems, "status": "attention" if email_problems else "healthy"},
        "in_app": {"created_24h": created, "unread_24h": unread, "by_kind": [{"kind": k, "count": c} for k, c in by_kind]},
        "push": {"subscriptions": push_subs or 0},
    }
