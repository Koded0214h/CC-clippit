"""Browser checks for customer account and money screens."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://localhost:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp/qa-customer"
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    ("notifications", "/dashboard/notifications"),
    ("payout-receipt", "/dashboard/payouts/receipt"),
    ("payout-account", "/dashboard/payout-account"),
    ("security", "/dashboard/security"),
    ("profile", "/dashboard/profile"),
    ("transactions", "/brand/transactions"),
    ("transaction-receipt", "/brand/transactions/CLP-0926-041"),
    ("brand-notifications", "/brand/notifications"),
    ("closeout", "/brand/campaigns/campus-chop/report"),
]


def no_overflow(page):
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    ), page.url


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    errors = []
    page.on("pageerror", lambda error: errors.append(f"{page.url}: {error}"))

    for name, route in ROUTES:
        response = page.goto(f"{BASE}{route}", wait_until="networkidle")
        assert response and response.ok, route
        assert page.locator(".customer-page, .receipt-page").first.is_visible(), route
        no_overflow(page)
        page.wait_for_timeout(450)
        page.screenshot(path=str(OUT / f"desktop-{name}.png"), full_page=True)

    # Notification read state and filtering.
    page.goto(f"{BASE}/dashboard/notifications", wait_until="networkidle")
    assert page.locator(".notification-tape > a.is-unread").count() == 2
    page.locator(".notification-tally button", has_text="Money").click()
    assert page.locator(".notification-tape > a").count() == 2
    page.get_by_role("button", name="Mark all as read").click()
    assert page.locator(".notification-tape > a.is-unread").count() == 0

    # Bank details, identity confirmation and successful verification.
    page.goto(f"{BASE}/dashboard/payout-account", wait_until="networkidle")
    rail = page.locator(".bank-setup-rail").bounding_box()
    rail_art = page.locator(".bank-setup-rail > img").bounding_box()
    assert rail and rail_art
    assert rail_art["x"] >= rail["x"] and rail_art["x"] + rail_art["width"] <= rail["x"] + rail["width"]
    assert rail_art["y"] >= rail["y"] and rail_art["y"] + rail_art["height"] <= rail["y"] + rail["height"]
    page.locator("input[inputmode=numeric]").fill("0123456789")
    assert "Tobi Adeyemi" in page.locator(".account-resolution").inner_text()
    page.get_by_role("button", name="Confirm this account").click()
    page.locator("input[autocomplete=one-time-code]").fill("204106")
    page.get_by_role("button", name="Verify payout account").click()
    assert "Bank account verified" in page.locator(".customer-head h1").inner_text()

    # Security controls change visibly and sessions can be revoked.
    page.goto(f"{BASE}/dashboard/security", wait_until="networkidle")
    orbit = page.locator(".security-orbit").bounding_box()
    score = page.locator(".security-orbit strong").bounding_box()
    assert orbit and score
    assert abs((score["x"] + score["width"] / 2) - (orbit["x"] + orbit["width"] / 2)) < 2
    page.locator(".security-toggle input").check()
    page.wait_for_function(
        "document.querySelector('.security-orbit strong')?.textContent?.includes('100%')"
    )
    before = page.locator(".sessions-sheet article").count()
    page.locator(".sessions-sheet article button").first.click()
    assert page.locator(".sessions-sheet article").count() == before - 1

    # Transaction selection updates its receipt; completed campaign exposes closeout.
    page.goto(f"{BASE}/brand/transactions", wait_until="networkidle")
    assert page.locator('.brand-alert').get_attribute("href") == "/brand/notifications"
    pot_size = page.locator(".transaction-balance > div > strong .animated-number").evaluate(
        "element => parseFloat(getComputedStyle(element).fontSize)"
    )
    assert pot_size >= 40, pot_size
    page.locator(".transaction-ledger header button", has_text="Refund").click()
    page.locator(".transaction-row").click()
    assert "REF-00812" in page.locator(".transaction-ticket").inner_text()
    assert page.locator('.transaction-ticket a[href$="/report"]').is_visible()
    assert "clippit-mark.png" in page.locator('.transaction-ticket img[alt="Clippit"]').get_attribute("src")

    # Brand notifications have their own feed and keep the bell badge in sync.
    page.evaluate("localStorage.removeItem('clippit:brand-notifications-read')")
    page.goto(f"{BASE}/brand/notifications", wait_until="networkidle")
    assert page.locator(".notification-tape > a.is-unread").count() == 4
    page.locator(".notification-tally button", has_text="Review").click()
    assert page.locator(".notification-tape > a").count() == 2
    page.get_by_role("button", name="Mark all as read").click()
    assert page.locator(".notification-tape > a.is-unread").count() == 0
    assert page.locator(".brand-alert b").count() == 0

    page.goto(f"{BASE}/brand/campaigns/campus-chop/report", wait_until="networkidle")
    assert page.locator(".closeout-proof article").count() == 4
    assert page.locator(".platform-delivery > div").count() == 3
    assert "clippit-mark.png" in page.locator('.closeout-receipt img[alt="Clippit"]').get_attribute("src")

    page.goto(f"{BASE}/dashboard/payouts/receipt", wait_until="networkidle")
    assert "clippit-mark.png" in page.locator('.payout-receipt img[alt="Clippit"]').get_attribute("src")
    assert "Official payout receipt" in page.locator(".payout-receipt").inner_text()

    page.goto(f"{BASE}/dashboard/profile", wait_until="networkidle")
    assert page.locator(".profile-work article").count() == 3
    assert page.locator(".public-passport > dl > div").count() == 4

    for width, height in [(1024, 768), (390, 844), (320, 720)]:
        page.set_viewport_size({"width": width, "height": height})
        for name, route in ROUTES:
            page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
            no_overflow(page)
            if route.startswith("/dashboard"):
                assert page.locator(".mobile-dock").is_visible() if width <= 900 else page.locator(".studio-rail").is_visible()
            else:
                assert page.locator(".brand-mobile-dock").is_visible() if width <= 900 else page.locator(".brand-rail").is_visible()
            if width == 390:
                page.wait_for_timeout(300)
                page.screenshot(path=str(OUT / f"mobile-{name}.png"), full_page=True)
            if width <= 390 and route == "/brand/transactions":
                assert not page.locator(".transaction-ticket").is_visible()
                page.locator(".transaction-row").first.click()
                page.wait_for_url("**/brand/transactions/CLP-0926-041")
                assert page.locator(".transaction-ticket--full").is_visible()

    # A fresh phone tab guards against shell-only captures on the bank route.
    phone = browser.new_page(viewport={"width": 390, "height": 844})
    phone.goto(f"{BASE}/dashboard/payout-account", wait_until="networkidle")
    assert phone.locator(".customer-head h1").inner_text() == "Payout account"
    assert phone.locator(".bank-setup-sheet").is_visible()
    no_overflow(phone)
    phone.wait_for_timeout(500)
    phone.screenshot(path=str(OUT / "mobile-payout-account-fresh.png"), full_page=True)
    phone.close()

    browser.close()
    assert not errors, errors
    print("PASS: customer account and money screens, brand notifications, interactions, and responsive widths.")
