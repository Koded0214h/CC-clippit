"""Responsive route checks for the 29 customer-completion screens."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://127.0.0.1:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp" / "qa-completion"
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    "/help",
    "/help/how-campaigns-work",
    "/support/tickets",
    "/support/tickets/new",
    "/support/tickets/CLP-2841",
    "/disputes",
    "/disputes/new",
    "/disputes/DSP-0419",
    "/account/data",
    "/account/delete",
    "/legal",
    "/legal/privacy",
    "/consent/update",
    "/verify/VIEW-21904",
    "/dashboard/verification",
    "/dashboard/verification/identity",
    "/dashboard/verification/documents",
    "/dashboard/verification/status",
    "/dashboard/earnings/statement",
    "/creators/tobioncam",
    "/brand/verification",
    "/brand/verification/business",
    "/brand/verification/documents",
    "/brand/verification/status",
    "/brand/team",
    "/brand/team/invite",
    "/brand/billing",
    "/brand/invoices/INV-0926-041",
    "/brand/campaigns/campus-chop/refund",
]
TARGET_ROUTE = os.getenv("CLIPPIT_ROUTE")
AUDIT_ROUTES = [TARGET_ROUTE] if TARGET_ROUTE else ROUTES

SHOTS = {
    "/review/customer-screens": "review-index",
    "/help": "help",
    "/account/data": "account-data",
    "/account/delete": "account-delete",
    "/legal": "legal-centre",
    "/support/tickets/CLP-2841": "support-thread",
    "/disputes/DSP-0419": "dispute-case",
    "/dashboard/verification": "creator-verification-start",
    "/dashboard/verification/documents": "creator-documents",
    "/dashboard/earnings/statement": "earnings-statement",
    "/creators/tobioncam": "public-profile",
    "/brand/verification": "brand-verification-start",
    "/brand/team": "brand-team",
    "/brand/billing": "brand-billing",
    "/brand/invoices/INV-0926-041": "brand-invoice",
    "/brand/campaigns/campus-chop/refund": "brand-refund",
}


def check_page(page, route):
    response = page.goto(f"{BASE}{route}", wait_until="networkidle")
    assert response and response.ok, f"{route}: HTTP {response.status if response else 'none'}"
    assert page.locator("h1").count() > 0, f"{route}: missing h1"
    assert page.locator("h1").first.is_visible(), f"{route}: h1 not visible"
    overflowing = page.evaluate("""() => [...document.querySelectorAll('body *')]
      .map(el => ({ tag: el.tagName, cls: el.className || '', parent: el.parentElement?.className || '', text: el.textContent?.trim().slice(0, 60), right: el.getBoundingClientRect().right, width: el.getBoundingClientRect().width }))
      .filter(item => item.right > window.innerWidth + 1)
      .slice(0, 8)""")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
        f"{route}: horizontal overflow "
        f"{page.evaluate('document.documentElement.scrollWidth')} > "
        f"{page.evaluate('window.innerWidth')}; elements={overflowing}"
    )
    blank_actions = page.locator("a, button").evaluate_all(
        "els => els.filter(el => !el.getAttribute('aria-label') && !el.textContent.trim() && !el.querySelector('svg')).length"
    )
    assert blank_actions == 0, f"{route}: {blank_actions} blank actions"
    clipped_statuses = page.locator(".completion-status").evaluate_all(
        "els => els.filter(el => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1).map(el => el.textContent.trim())"
    )
    assert not clipped_statuses, f"{route}: clipped status labels {clipped_statuses}"
    if page.locator(".statement-download").count():
        style = page.locator(".statement-download").evaluate(
            "el => ({color: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor})"
        )
        assert style["color"] != style["background"], f"{route}: invisible download label"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    errors = []
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda error: errors.append(str(error)))

    assert len(ROUTES) == 29
    for width, height, label in [(1440, 1000, "desktop"), (390, 844, "mobile"), (320, 780, "small-mobile")]:
        page.set_viewport_size({"width": width, "height": height})
        for route in AUDIT_ROUTES:
            check_page(page, route)
            if TARGET_ROUTE and route in SHOTS and label != "small-mobile":
                page.wait_for_timeout(600)
                page.screenshot(path=str(OUT / f"{label}-{SHOTS[route]}.png"), full_page=True)
        if not TARGET_ROUTE:
            page.goto(f"{BASE}/review/customer-screens", wait_until="networkidle")
            assert page.locator(".review-index section a").count() == 29
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        if label != "small-mobile" and not TARGET_ROUTE:
            for route, name in SHOTS.items():
                page.goto(f"{BASE}{route}", wait_until="networkidle")
                page.wait_for_timeout(1400)
                page.screenshot(path=str(OUT / f"{label}-{name}.png"), full_page=True)

    if not TARGET_ROUTE:
        page.set_viewport_size({"width": 390, "height": 844})

        page.goto(f"{BASE}/dashboard", wait_until="networkidle")
        page.locator(".mobile-dock button", has_text="More").click()
        creator_more = page.locator(".creator-mobile-more")
        assert creator_more.is_visible(), "creator: More menu did not open"
        creator_hrefs = creator_more.locator("a").evaluate_all("els => els.map(el => el.getAttribute('href'))")
        for href in ["/dashboard/settings", "/dashboard/leaderboard", "/dashboard/verification", "/account/data", "/help", "/support/tickets", "/disputes", "/legal"]:
            assert href in creator_hrefs, f"creator: missing mobile navigation link {href}"
        page.screenshot(path=str(OUT / "mobile-creator-more.png"), full_page=False)
        creator_more.locator('a[href="/legal"]').click()
        page.wait_for_url(f"{BASE}/legal")
        assert page.locator('.service-bar nav a[href="/account/data"]').is_visible(), "service navigation: Account link hidden on mobile"
        assert page.locator('.service-bar nav a[href="/legal"]').is_visible(), "service navigation: Legal link hidden on mobile"
        page.screenshot(path=str(OUT / "mobile-legal-navigation.png"), full_page=False)

        page.goto(f"{BASE}/brand", wait_until="networkidle")
        page.locator(".brand-mobile-dock button", has_text="More").click()
        brand_more = page.locator(".brand-mobile-more")
        assert brand_more.is_visible(), "brand: More menu did not open"
        brand_hrefs = brand_more.locator("a").evaluate_all("els => els.map(el => el.getAttribute('href'))")
        for href in ["/brand/transactions", "/brand/team", "/brand/billing", "/brand/verification", "/brand/settings", "/account/data", "/help", "/support/tickets", "/disputes", "/legal"]:
            assert href in brand_hrefs, f"brand: missing mobile navigation link {href}"
        page.screenshot(path=str(OUT / "mobile-brand-more.png"), full_page=False)

    assert not errors, f"Browser page errors: {errors}"
    browser.close()

print(f"Verified {len(AUDIT_ROUTES)} customer screens at desktop, mobile and 320px widths.")
