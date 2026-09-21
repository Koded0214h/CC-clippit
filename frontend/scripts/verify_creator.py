"""Interaction and responsive checks for the complete creator journey."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://localhost:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp/qa-creator"
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    ("clips", "/dashboard/clips"),
    ("accounts", "/dashboard/accounts"),
    ("submit", "/dashboard/campaigns/indomie-no-long-thing/submit"),
    ("processing", "/dashboard/submissions/processing"),
    ("approved", "/dashboard/submissions/approved"),
    ("rejected", "/dashboard/submissions/rejected"),
    ("appeal", "/dashboard/submissions/appeal"),
    ("earnings", "/dashboard/earnings"),
    ("withdraw", "/dashboard/withdraw"),
    ("receipt", "/dashboard/payouts/receipt"),
]


def no_overflow(page):
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    ), page.url


def wait_for_text(page, selector, expected):
    page.wait_for_function(
        "([selector, expected]) => document.querySelector(selector)?.textContent?.includes(expected)",
        arg=[selector, expected],
    )


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    errors = []
    page.on("pageerror", lambda error: errors.append(f"{page.url}: {error}"))

    for index, (name, route) in enumerate(ROUTES, start=1):
        response = page.goto(f"{BASE}{route}", wait_until="networkidle")
        assert response and response.ok, route
        assert page.locator(".creator-flow-page").is_visible(), route
        no_overflow(page)
        if name in {"clips", "accounts", "submit", "processing", "approved", "rejected", "earnings", "withdraw", "receipt"}:
            page.screenshot(
                path=str(OUT / f"{index:02d}-{name}-desktop.png"), full_page=True
            )

    # Account state is interactive and visibly changes its readiness score.
    page.goto(f"{BASE}/dashboard/accounts", wait_until="networkidle")
    page.wait_for_timeout(150)
    assert "2/3" in page.locator(".connect-score").inner_text()
    connected_badge = page.locator(".account-card .creator-status").first.bounding_box()
    assert connected_badge and connected_badge["width"] < 130 and connected_badge["height"] < 45
    assert page.locator(".connect-stage .creator-art img").is_visible()
    page.locator(".account-card").last.locator("button").click()
    wait_for_text(page, ".connect-score", "3/3")

    # Custom animated illustrations are gone; feature panels use static Clippit artwork.
    page.goto(f"{BASE}/dashboard/earnings", wait_until="domcontentloaded")
    assert page.locator(".motion-art").count() == 0
    assert page.locator(".earnings-stage .creator-art img").is_visible()
    payable = page.locator(".earnings-total .animated-number").first
    early_payable = payable.inner_text()
    wait_for_text(page, ".earnings-total .animated-number", "18,400")
    page.wait_for_selector(".earnings-total .animated-number.is-settled")
    assert payable.inner_text() != early_payable
    assert payable.evaluate("node => node.classList.contains('is-settled')")
    wait_for_text(page, ".earnings-buckets article:nth-child(2) > strong", "184,450")
    bucket_total = page.locator(".earnings-buckets article:nth-child(2) > strong")
    assert float(bucket_total.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")) >= 24

    # Submission validates, saves, then enters verification.
    page.goto(
        f"{BASE}/dashboard/campaigns/indomie-no-long-thing/submit",
        wait_until="networkidle",
    )
    page.locator(".submission-submit").click()
    assert "Paste the public link" in page.locator(".creator-error").inner_text()
    page.locator("input[inputmode=url]").fill(
        "https://www.tiktok.com/@tobioncam/video/demo"
    )
    page.locator(".submission-submit").click()
    page.wait_for_url("**/dashboard/submissions/processing")

    # Appeal cannot submit without a useful reason, then resolves to confirmation.
    page.goto(f"{BASE}/dashboard/submissions/appeal", wait_until="networkidle")
    assert page.locator(".appeal-form button[type=submit]").is_disabled()
    page.locator("textarea").fill(
        "The required tag is visible after expanding the full public caption."
    )
    page.locator(".appeal-form button[type=submit]").click()
    assert page.locator(".appeal-success").is_visible()

    # A withdrawal carries its chosen value into the receipt.
    page.goto(f"{BASE}/dashboard/withdraw", wait_until="networkidle")
    page.locator(".amount-chips button").nth(1).click()
    assert page.locator(".amount-field input").input_value() == "10000"
    page.locator(".withdraw-form button[type=submit]").click()
    page.wait_for_url("**/dashboard/payouts/receipt")
    wait_for_text(page, ".payout-receipt__summary strong", "10,000")
    page.locator(".receipt-hero").scroll_into_view_if_needed()
    wait_for_text(page, ".receipt-hero h1", "10,000")
    assert page.locator('.payout-receipt img[alt="Clippit"]').is_visible()
    assert "₦10,000" in page.locator(".payout-receipt__summary strong").inner_text()
    assert page.locator(".payout-receipt__summary .animated-number").count() == 0
    assert "Download receipt" in page.locator(".receipt-actions button").inner_text()

    # Existing campaign detail now enters the new journey after joining.
    page.goto(
        f"{BASE}/dashboard/campaigns/indomie-no-long-thing",
        wait_until="networkidle",
    )
    page.locator(".campaign-detail-hero__action button").click()
    assert page.locator(".campaign-detail-hero__action a").get_attribute("href").endswith(
        "/submit"
    )

    # All ten surfaces must remain usable at laptop, tablet, and small-phone widths.
    for width, height in [(1366, 768), (1024, 768), (820, 1180), (390, 844), (320, 720)]:
        page.set_viewport_size({"width": width, "height": height})
        for name, route in ROUTES:
            page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
            no_overflow(page)
            if width <= 820:
                assert page.locator(".mobile-dock").is_visible(), route
                assert page.locator(".mobile-dock a").count() == 5
            if width <= 390:
                for art_panel in page.locator(".creator-art").all():
                    art_box = art_panel.bounding_box()
                    assert art_box and art_box["width"] <= 130 and art_box["height"] <= 140, (route, art_box)
        if width in {1366, 390, 320}:
            page.goto(f"{BASE}/dashboard/earnings", wait_until="domcontentloaded")
            page.screenshot(
                path=str(OUT / f"responsive-earnings-{width}.png"), full_page=True
            )
            page.goto(f"{BASE}/dashboard/clips", wait_until="domcontentloaded")
            page.screenshot(
                path=str(OUT / f"responsive-clips-{width}.png"), full_page=True
            )
        if width == 390:
            page.goto(f"{BASE}/dashboard/accounts", wait_until="domcontentloaded")
            page.screenshot(path=str(OUT / "responsive-accounts-390.png"), full_page=True)
            page.goto(f"{BASE}/dashboard/submissions/processing", wait_until="domcontentloaded")
            page.screenshot(path=str(OUT / "responsive-processing-390.png"), full_page=True)
            page.goto(f"{BASE}/dashboard/withdraw", wait_until="domcontentloaded")
            page.locator(".withdraw-form button[type=submit]").scroll_into_view_if_needed()
            page.wait_for_timeout(250)
            assert "is-hidden" in (page.locator(".mobile-dock").get_attribute("class") or "")
            page.screenshot(path=str(OUT / "responsive-withdraw-390.png"), full_page=True)

    browser.close()
    assert not errors, errors
    print("PASS: all 10 creator screens, interactions, and five responsive widths.")
