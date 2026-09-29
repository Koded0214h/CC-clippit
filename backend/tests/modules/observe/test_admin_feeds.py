"""Admin-app feeds behind the normal operator login."""

from tests.http_app import api, auth, make_admin, signup  # noqa: F401


async def test_feeds_require_an_admin(api):
    _, creator = await signup(api, "creator")
    for path in ("/admin/system/health", "/admin/delivery/webhooks", "/admin/delivery/social", "/admin/delivery/notifications"):
        assert (await api.get(path)).status_code in (401, 403)
        assert (await api.get(path, headers=auth(creator))).status_code == 403


async def test_system_health_shape(api):
    admin = await make_admin(api)
    d = (await api.get("/admin/system/health", headers=auth(admin))).json()
    names = [s["name"] for s in d["services"]]
    assert names[:2] == ["API", "Database"] and len(d["series"]) == 30
    assert d["services"][1]["status"] == "operational"
    host = next(x for x in d["services"] if x["name"] == "Host resources")
    assert "CPU" in host["metric"] and "RAM" in host["metric"]


async def test_webhook_feed_counts_rejected_deliveries(api):
    admin = await make_admin(api)
    bad = await api.post("/webhooks/payments", content=b"{}", headers={"x-paystack-signature": "nope"})
    assert bad.status_code in (401, 400, 403)
    d = (await api.get("/admin/delivery/webhooks", headers=auth(admin))).json()
    payments = next(g for g in d["groups"] if g["name"] == "Payments provider")
    assert payments["events"] >= 1 and payments["rejected"] >= 1
    assert any(r["path"] == "/webhooks/payments" for r in d["recent"])


async def test_social_and_notification_feeds(api):
    admin = await make_admin(api)
    social = (await api.get("/admin/delivery/social", headers=auth(admin))).json()
    assert {p["name"] for p in social["platforms"]} >= {"tiktok", "instagram"}
    n = (await api.get("/admin/delivery/notifications", headers=auth(admin))).json()
    assert n["in_app"]["created_24h"] >= 0 and "email" in n and "push" in n
