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

SHOTS = {
    "/review/customer-screens": "review-index",
    "/help": "help",
    "/support/tickets/CLP-2841": "support-thread",
    "/disputes/DSP-0419": "dispute-case",
    "/dashboard/verification/documents": "creator-documents",
    "/dashboard/earnings/statement": "earnings-statement",
    "/creators/tobioncam": "public-profile",
    "/brand/team": "brand-team",
    "/brand/invoices/INV-0926-041": "brand-invoice",
    "/brand/campaigns/campus-chop/refund": "brand-refund",
}


def check_page(page, route):
    response = page.goto(f"{BASE}{route}", wait_until="networkidle")
    assert response and response.ok, f"{route}: HTTP {response.status if response else 'none'}"
    assert page.locator("h1").count() > 0, f"{route}: missing h1"
    assert page.locator("h1").first.is_visible(), f"{route}: h1 not visible"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
        f"{route}: horizontal overflow "
        f"{page.evaluate('document.documentElement.scrollWidth')} > "
        f"{page.evaluate('window.innerWidth')}"
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
        for route in ROUTES:
            check_page(page, route)
        page.goto(f"{BASE}/review/customer-screens", wait_until="networkidle")
        assert page.locator(".review-index section a").count() == 29
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        if label != "small-mobile":
            for route, name in SHOTS.items():
                page.goto(f"{BASE}{route}", wait_until="networkidle")
                page.wait_for_timeout(1400)
                page.screenshot(path=str(OUT / f"{label}-{name}.png"), full_page=True)

    assert not errors, f"Browser page errors: {errors}"
    browser.close()

print(f"Verified {len(ROUTES)} customer screens at desktop, mobile and 320px widths.")
