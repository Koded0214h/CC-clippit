"""Browser-level checks for the engagement campaign experience."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from playwright.sync_api import Route, sync_playwright


BASE = os.getenv("CLIPPIT_BASE", "http://127.0.0.1:5174")
role = "organisation"


CAMPAIGN = {
    "id": "11111111-1111-4111-8111-111111111111",
    "slug": "live-hybrid",
    "event_manager_id": "22222222-2222-4222-8222-222222222222",
    "brand": {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "Gbedu Records",
        "photo_url": None,
        "verified": True,
    },
    "title": "Weekend listening room",
    "tagline": "Show where the new record belongs in your weekend.",
    "description": "Create an original short video using the campaign sound.",
    "category": "Music",
    "source_link": "https://gbedu.example/brief",
    "cover_image_url": None,
    "expected_views": 1_000_000,
    "platforms": ["tiktok", "instagram"],
    "status": "active",
    "phase": "Live",
    "accepting_entries": True,
    "payouts_frozen": False,
    "access_mode": "public",
    "invite_code": None,
    "assets": [],
    "end_condition": "budget",
    "video_cap": 50_000,
    "max_submissions": 3,
    "duration_days": None,
    "ends_at": None,
    "time_left": None,
    "pot": 500_000,
    "spent": 82_750,
    "remaining": 417_250,
    "payout_rule": {
        "rate_per_1000_views": 500,
        "cap_amount": 75_000,
        "video_cap_amount": 50_000,
        "max_submissions": 3,
        "min_views_threshold": 0,
    },
    "performance_metrics": [
        {
            "id": "31111111-1111-4111-8111-111111111111",
            "metric_type": "visit",
            "rate_amount": 15,
            "unit_size": 1,
            "min_threshold": 0,
            "verification_method": "tracked_link",
            "position": 0,
        },
        {
            "id": "32222222-2222-4222-8222-222222222222",
            "metric_type": "signup",
            "rate_amount": 250,
            "unit_size": 1,
            "min_threshold": 0,
            "verification_method": "server_event",
            "position": 1,
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "metric_type": "purchase",
            "rate_amount": 1000,
            "unit_size": 1,
            "min_threshold": 0,
            "verification_method": "server_event",
            "position": 2,
        },
    ],
    "conversion_setup": {
        "destination_type": "website",
        "destination_url": "https://shop.example/new-record",
        "whatsapp_number": None,
        "attribution_window_days": 30,
        "attribution_model": "last_touch",
    },
    "rules": [],
    "feed_status": "Joined",
    "joined": True,
    "metrics": None,
    "created_at": "2026-09-28T10:00:00Z",
    "updated_at": "2026-09-28T10:00:00Z",
}

DRAFT = {
    "id": "55555555-5555-4555-8555-555555555555",
    "schema_version": 1,
    "status": "in_progress",
    "step": "metrics",
    "revision": 0,
    "answers": {
        "title": "Weekend listening room",
        "description": "Create an original short video using the campaign sound.",
        "platforms": ["tiktok", "instagram"],
        "pot": 500000,
        "payout_rule": {
            "rate_per_1000_views": 500,
            "cap_amount": 75000,
            "video_cap_amount": 50000,
            "max_submissions": 3,
            "min_views_threshold": 1000,
        },
        "duration_days": 14,
        "rules": [],
        "access_mode": "public",
        "assets": [],
        "end_condition": "duration",
        "performance_metrics": [
            {
                "metric_type": "view",
                "rate_amount": 500,
                "unit_size": 1000,
                "min_threshold": 1000,
            }
        ],
        "conversion_setup": None,
    },
    "blockers": {},
    "finalized_campaign_id": None,
    "created_at": "2026-09-28T10:00:00Z",
    "updated_at": "2026-09-28T10:00:00Z",
}


def json_response(route: Route, body, status: int = 200):
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def handle_api(route: Route):
    request = route.request
    if request.resource_type not in {"fetch", "xhr"}:
        route.continue_()
        return
    path = urlparse(request.url).path
    method = request.method
    if path == "/auth/me":
        json_response(
            route,
            {
                "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "email": f"{role}@example.com",
                "full_name": "Performance Tester",
                "role": role,
                "created_at": "2026-09-28T10:00:00Z",
                "email_verified": True,
                "onboarding_completed": True,
            },
        )
    elif path == "/campaigns/live-hybrid" and method == "GET":
        json_response(route, CAMPAIGN)
    elif path == "/campaign-drafts" and method == "GET":
        json_response(route, [DRAFT])
    elif path == f"/campaign-drafts/{DRAFT['id']}" and method == "PATCH":
        body = json.loads(request.post_data or "{}")
        answers = {**DRAFT["answers"], **{key: value for key, value in body.items() if key not in {"revision", "step"}}}
        json_response(route, {**DRAFT, "revision": int(body.get("revision", 0)) + 1, "step": body.get("step"), "answers": answers})
    elif path == "/campaigns/live-hybrid/stats":
        json_response(
            route,
            {
                "campaign_id": CAMPAIGN["id"],
                "phase": "Live",
                "accepting_entries": True,
                "pot": 500_000,
                "spent": 82_750,
                "remaining": 417_250,
                "percent_remaining": 83.45,
                "verified_views": 0,
                "views_last_24h": 0,
                "submissions": 12,
                "approved": 8,
                "review": 2,
                "checking": 2,
                "rejected": 0,
                "time_left": None,
                "last_reading_at": "2026-09-28T12:00:00Z",
                "performance": {"visit": 1840, "signup": 93, "purchase": 28},
            },
        )
    elif path == "/campaigns/live-hybrid/submissions":
        json_response(route, [])
    elif path == "/campaigns/live-hybrid/integration-secret" and method == "POST":
        json_response(
            route,
            {
                "campaign_id": CAMPAIGN["id"],
                "secret": "clp_live_browser_test_secret",
                "last_four": "cret",
                "warning": "Copy this secret now. It will not be shown again.",
            },
        )
    elif path == "/campaigns/live-hybrid/attribution-links" and method == "POST":
        json_response(
            route,
            {
                "id": "44444444-4444-4444-8444-444444444444",
                "campaign_id": CAMPAIGN["id"],
                "short_code": "A1B2C3D4",
                "tracking_url": "https://clippit-5b5j.onrender.com/t/clp_browser_test",
                "destination_url": "https://shop.example/new-record?clippit_ref=A1B2C3D4",
                "expires_at": "2026-10-28T10:00:00Z",
            },
            201,
        )
    elif "leaderboard" in path:
        json_response(route, {"items": [], "total": 0})
    elif path.endswith("/product/config") or path == "/product/config":
        json_response(route, {"hold_days": 5})
    else:
        json_response(route, {"detail": "not mocked"}, 404)


def no_horizontal_overflow(page):
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    ), page.url


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
    context.add_init_script(
        """
        localStorage.setItem('clippit:access-token', 'browser-test-token');
        localStorage.removeItem('clippit:brand-campaign-draft');
        """
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", handle_api)

    page.goto(f"{BASE}/brand/campaigns/new/metrics", wait_until="networkidle")
    page.get_by_role("heading", name="What should this campaign achieve?").wait_for()
    assert page.locator(".metric-studio__rail article").count() == 7
    assert page.locator(".metric-studio__rail article.is-selected").count() == 1

    for label in ("Comments", "Shares", "Purchases"):
        card = page.locator(".metric-studio__rail article").filter(has_text=label)
        card.locator("button").click()
        assert "is-selected" in (card.get_attribute("class") or "")

    page.get_by_role("heading", name="Where should customers go?").wait_for()
    next_link = page.get_by_role("link", name="Set earning limits")
    assert next_link.get_attribute("aria-disabled") == "true"
    page.get_by_placeholder("https://yourstore.com/products").fill(
        "https://shop.example/product"
    )
    assert next_link.get_attribute("aria-disabled") == "false"

    page.get_by_role("button", name="WhatsApp orders").click()
    page.get_by_placeholder("2348012345678").fill("+234 801 234 5678")
    page.get_by_label("Attribution window").select_option("14")
    page.get_by_label("Credit goes to").select_option("first_touch")
    assert next_link.get_attribute("href") == "/brand/campaigns/new/rules"

    for width, height in ((1440, 1000), (1024, 768), (390, 844), (320, 720)):
        page.set_viewport_size({"width": width, "height": height})
        no_horizontal_overflow(page)
        assert page.locator(".conversion-route").is_visible()

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE}/brand/campaigns/live-hybrid", wait_until="networkidle")
    page.get_by_role("heading", name="Results being measured").wait_for()
    assert page.locator(".live-performance-strip article").count() == 3
    page.get_by_role("heading", name="Connect confirmed customer actions").wait_for()
    no_horizontal_overflow(page)
    page.get_by_role("button", name="Create setup key").click()
    page.get_by_text("Copy now. It will not be shown again.", exact=True).wait_for()
    assert page.locator(".campaign-integration-card__secret code").inner_text() == (
        "clp_live_browser_test_secret"
    )
    page.get_by_role("button", name="Copy setup key").click()
    page.get_by_role("button", name="Copied").wait_for()

    role = "creator"
    page.goto(f"{BASE}/dashboard/campaigns/live-hybrid", wait_until="networkidle")
    page.get_by_role("heading", name="Performance scorecard").wait_for()
    assert page.locator(".campaign-outcome-grid article").count() == 3
    page.get_by_text("Create your creator-specific link", exact=True).wait_for()
    page.get_by_role("button", name="Create and copy").click()
    page.get_by_text(
        "https://clippit-5b5j.onrender.com/t/clp_browser_test", exact=True
    ).wait_for()
    assert page.get_by_role("button", name="Copy again").is_visible()
    no_horizontal_overflow(page)

    browser.close()
    assert not errors, errors

print("PASS: performance campaign builder, brand integration key, creator tracking link, and four responsive widths.")
