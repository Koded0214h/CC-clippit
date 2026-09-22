"""Responsive and interaction checks for the locked 32 admin screens."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://127.0.0.1:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp" / "qa-admin"
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    "/admin/login", "/admin", "/admin/users", "/admin/users/USR-18402",
    "/admin/creators/verifications", "/admin/creators/verifications/KYC-2038",
    "/admin/brands/verifications", "/admin/brands/verifications/KYB-0918",
    "/admin/campaigns", "/admin/campaigns/no-long-thing",
    "/admin/submissions", "/admin/submissions/SUB-1042",
    "/admin/support", "/admin/support/CLP-2914",
    "/admin/disputes", "/admin/disputes/DSP-0419",
    "/admin/payouts", "/admin/payouts/PAY-90241",
    "/admin/refunds", "/admin/refunds/RFD-1840",
    "/admin/ledger", "/admin/reconciliation", "/admin/risk", "/admin/risk/RSK-7712",
    "/admin/social-connections", "/admin/webhooks", "/admin/notifications",
    "/admin/operators", "/admin/operators/invite", "/admin/roles", "/admin/audit", "/admin/system",
]
TARGET_ROUTE = os.getenv("CLIPPIT_ROUTE")
AUDIT_ROUTES = [TARGET_ROUTE] if TARGET_ROUTE else ROUTES

SHOTS = {
    "/admin/login": "login", "/admin": "command", "/admin/users": "customers",
    "/admin/creators/verifications/KYC-2038": "creator-review",
    "/admin/submissions/SUB-1042": "submission-review", "/admin/payouts": "payouts",
    "/admin/ledger": "ledger", "/admin/reconciliation": "reconciliation",
    "/admin/social-connections": "providers", "/admin/operators/invite": "operator-invite",
    "/admin/roles": "roles", "/admin/audit": "audit", "/admin/system": "system",
}


def check_page(page, route):
    response = page.goto(f"{BASE}{route}", wait_until="networkidle")
    assert response and response.ok, f"{route}: HTTP {response.status if response else 'none'}"
    assert page.locator("h1").count() > 0 and page.locator("h1").first.is_visible(), f"{route}: missing visible h1"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
        f"{route}: horizontal overflow {page.evaluate('document.documentElement.scrollWidth')} > {page.evaluate('window.innerWidth')}"
    )
    blank = page.locator("a, button").evaluate_all(
        "els => els.filter(el => !el.getAttribute('aria-label') && !el.textContent.trim() && !el.querySelector('svg,img')).length"
    )
    assert blank == 0, f"{route}: {blank} blank actions"
    clipped = page.locator(".admin-status").evaluate_all(
        "els => els.filter(el => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1).map(el => ({text: el.textContent.trim(), scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, display: getComputedStyle(el).display, fontSize: getComputedStyle(el).fontSize}))"
    )
    assert not clipped, f"{route}: clipped status labels {clipped}"


with sync_playwright() as playwright:
    assert len(ROUTES) == 32
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    for width, height, label in [(1440, 1000, "desktop"), (390, 844, "mobile"), (320, 780, "small-mobile")]:
        page.set_viewport_size({"width": width, "height": height})
        for route in AUDIT_ROUTES:
            check_page(page, route)
            if width != 320 and route in SHOTS:
                page.wait_for_timeout(1400)
                page.screenshot(path=str(OUT / f"{label}-{SHOTS[route]}.png"), full_page=True)

    if not TARGET_ROUTE:
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{BASE}/admin", wait_until="networkidle")
        page.locator(".admin-mobile-dock button", has_text="More").click()
        assert page.locator(".admin-more").is_visible(), "mobile More menu did not open"
        menu_hrefs = page.locator(".admin-more a").evaluate_all("els => els.map(el => el.getAttribute('href'))")
        for href in ["/admin/creators/verifications", "/admin/brands/verifications", "/admin/campaigns", "/admin/support", "/admin/disputes", "/admin/refunds", "/admin/ledger", "/admin/reconciliation", "/admin/risk", "/admin/social-connections", "/admin/webhooks", "/admin/notifications", "/admin/operators", "/admin/roles", "/admin/audit", "/admin/system"]:
            assert href in menu_hrefs, f"mobile menu missing {href}"
        page.screenshot(path=str(OUT / "mobile-all-tools.png"), full_page=False)

        page.goto(f"{BASE}/admin/submissions/SUB-1042", wait_until="networkidle")
        page.get_by_role("button", name="Approve submission").click()
        assert page.locator(".admin-decision-saved").is_visible(), "case decision did not confirm"

        page.goto(f"{BASE}/admin/operators/invite", wait_until="networkidle")
        page.get_by_role("button", name="Send secure invitation").click()
        assert page.get_by_text("Invitation sent", exact=True).is_visible(), "operator invitation did not confirm"

        page.goto(f"{BASE}/admin/system", wait_until="networkidle")
        page.locator(".admin-runtime-controls input").check()
        assert page.get_by_text("Maintenance notice will appear", exact=False).is_visible(), "system control did not show approval state"

    assert not errors, f"Browser page errors: {errors}"
    browser.close()

print(f"Verified {len(AUDIT_ROUTES)} admin screens at desktop, mobile and 320px widths.")
