"""Admin-app ops feeds (REST) behind the normal operator login."""

from tests.http_app import api, auth, make_admin, signup  # noqa: F401

PATHS = ("/admin/system/health", "/admin/delivery/webhooks", "/admin/delivery/social", "/admin/delivery/notifications", "/admin/ops/snapshot")


async def test_feeds_require_an_admin(api):
    _, creator = await signup(api, "creator")
    for path in PATHS:
        assert (await api.get(path)).status_code in (401, 403)
        assert (await api.get(path, headers=auth(creator))).status_code == 403


async def test_system_health_contract(api):
    admin = await make_admin(api)
    d = (await api.get("/admin/system/health", headers=auth(admin))).json()
    keys = [s["key"] for s in d["services"]]
    assert keys == ["api", "database", "jobs", "media_checks", "storage", "host"]
    for s in d["services"]:
        assert {"name", "status", "headline", "availability_30d", "trend", "detail"} <= s.keys()
        assert {"label", "display"} <= s["headline"].keys()
    db = next(s for s in d["services"] if s["key"] == "database")
    assert db["status"] == "operational"
    assert d["status"] in ("operational", "degraded", "down") and len(d["series"]) == 30
    assert next(s for s in d["services"] if s["key"] == "media_checks")["checking"] == 0


async def test_availability_comes_from_persisted_samples(api):
    from datetime import datetime, timedelta, timezone

    from modules.observe.models import OpsHealthSample

    admin = await make_admin(api)
    assert next(s for s in (await api.get("/admin/system/health", headers=auth(admin))).json()["services"] if s["key"] == "api")["availability_30d"] is None
    # 10 good minutes out of the last 20 expected → ~50%
    from core.deps import get_db
    from main import app

    async for db in app.dependency_overrides[get_db]():
        start = datetime.now(timezone.utc) - timedelta(minutes=20)
        for i in range(0, 20, 2):
            db.add(OpsHealthSample(service="api", ok=True, ts=start + timedelta(minutes=i)))
        await db.commit()
    got = next(s for s in (await api.get("/admin/system/health", headers=auth(admin))).json()["services"] if s["key"] == "api")["availability_30d"]
    assert 40 <= got <= 60


async def test_webhook_feed_counts_rejected_deliveries(api):
    admin = await make_admin(api)
    bad = await api.post("/webhooks/payments", content=b"{}", headers={"x-paystack-signature": "nope"})
    assert bad.status_code in (401, 400, 403)
    d = (await api.get("/admin/delivery/webhooks", headers=auth(admin))).json()
    assert d["kind"] == "webhooks" and d["status"] in ("healthy", "attention", "failing")
    payments = next(c for c in d["cards"] if c["key"] == "payments")
    assert payments["facts"]["events"] >= 1 and payments["facts"]["rejected"] >= 1 and payments["status"] == "attention"
    assert len(payments["window"]["buckets"]) == 60
    assert payments["events"][0]["result"] == "rejected" and payments["events"][0]["id"].startswith("WEBHOOKS-")


async def test_social_feed_lists_every_platform(api):
    admin = await make_admin(api)
    d = (await api.get("/admin/delivery/social", headers=auth(admin))).json()
    cards = {c["key"]: c for c in d["cards"]}
    assert {"tiktok", "instagram"} <= cards.keys()
    assert {"configured", "connected", "expired_tokens", "tracked_posts", "delayed_checks"} <= cards["tiktok"]["facts"].keys()


async def test_notification_feed_counts_email_sends(api):
    from core import delivery_stats

    admin = await make_admin(api)
    delivery_stats.record("email", True, 120.0)
    delivery_stats.record("email", False, 30.0, "SMTPException")
    d = (await api.get("/admin/delivery/notifications", headers=auth(admin))).json()
    cards = {c["key"]: c for c in d["cards"]}
    assert {"email", "in_app", "push"} == cards.keys()
    assert cards["email"]["facts"]["attempts"] >= 2 and cards["email"]["status"] in ("attention", "failing")
    assert any(e["result"] == "failed" for e in cards["email"]["events"])


async def test_snapshot_has_all_topics(api):
    admin = await make_admin(api)
    d = (await api.get("/admin/ops/snapshot", headers=auth(admin))).json()
    assert set(d) == {"system", "webhooks", "social", "notifications"}
