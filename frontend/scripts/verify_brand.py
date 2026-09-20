"""Interaction, route and responsive checks for the complete brand workspace."""

import base64
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://localhost:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp/qa-brand"
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    ("overview", "/brand"),
    ("campaigns", "/brand/campaigns"),
    ("basics", "/brand/campaigns/new"),
    ("brief", "/brand/campaigns/new/brief"),
    ("platforms", "/brand/campaigns/new/platforms"),
    ("rules", "/brand/campaigns/new/rules"),
    ("budget", "/brand/campaigns/new/budget"),
    ("review", "/brand/campaigns/new/review"),
    ("fund", "/brand/campaigns/new/fund"),
    ("funded", "/brand/campaigns/new/funded"),
    ("live", "/brand/campaigns/no-long-thing"),
    ("queue", "/brand/reviews"),
    ("decision", "/brand/reviews/submission-1042"),
    ("settings", "/brand/settings"),
]


def no_overflow(page):
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    ), page.url


def images_loaded(page):
    broken = page.evaluate(
        "Array.from(document.images).filter(img => img.complete && img.naturalWidth === 0).map(img => img.src)"
    )
    assert not broken, (page.url, broken)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    errors = []
    page.on("pageerror", lambda error: errors.append(f"{page.url}: {error}"))

    for index, (name, route) in enumerate(ROUTES, start=1):
        response = page.goto(f"{BASE}{route}", wait_until="networkidle")
        assert response and response.ok, route
        assert page.locator(".brand-page, .brand-builder-page").first.is_visible(), route
        no_overflow(page)
        images_loaded(page)
        if name in {"overview", "brief", "budget", "live", "queue", "decision"}:
            page.wait_for_timeout(1400)
            page.screenshot(path=str(OUT / f"{index:02d}-{name}-desktop.png"), full_page=True)

    # The builder behaves like one connected campaign studio.
    page.goto(f"{BASE}/brand/campaigns/new", wait_until="networkidle")
    page.locator("input").first.fill("After-hours rescue")
    page.locator("textarea").fill("Show the tiny meal ritual that gets people through the work nobody sees.")
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/brand/campaigns/new/brief")
    assert "After-hours rescue" in page.locator(".builder-live-card").inner_text()
    before = page.locator(".brief-list li").count()
    page.locator(".brief-entry input").fill("Keep the product pack readable for two seconds.")
    page.locator(".brief-entry button").click()
    assert page.locator(".brief-list li").count() == before + 1

    page.goto(f"{BASE}/brand/campaigns/new/platforms", wait_until="networkidle")
    youtube = page.locator(".platform-picker > button").filter(has_text="YouTube")
    youtube.click()
    assert "is-selected" in (youtube.get_attribute("class") or "")

    page.goto(f"{BASE}/brand/campaigns/new/budget", wait_until="networkidle")
    page.locator(".budget-inputs input").first.fill("600000")
    page.locator(".budget-inputs input").nth(1).fill("600")
    page.wait_for_function(
        "document.querySelector('.budget-equation .is-answer')?.textContent?.includes('1M')"
    )

    # Funding confirmation opens the campaign room.
    page.goto(f"{BASE}/brand/campaigns/new/fund", wait_until="networkidle")
    page.locator(".funding-agreement").click()
    page.locator(".funding-checkout button[type=submit]").click()
    page.wait_for_url("**/brand/campaigns/new/funded")
    assert "Campaign funded" in page.locator(".funded-hero h1").inner_text()

    # Human review records an explicit decision.
    page.goto(f"{BASE}/brand/reviews/submission-1042", wait_until="networkidle")
    page.locator(".decision-actions button").last.click()
    assert "Clip approved" in page.locator(".review-resolved h1").inner_text()

    # Brand identity edits persist and refresh the shell immediately.
    page.goto(f"{BASE}/brand/settings", wait_until="networkidle")
    page.locator(".brand-profile-fields input").first.fill("Gbedu Studios")
    page.locator(".brand-profile-fields textarea").fill("Independent Lagos music and culture studio.")
    page.locator(".profile-photo-input").set_input_files({
        "name": "brand.png",
        "mimeType": "image/png",
        "buffer": base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="),
    })
    page.wait_for_selector(".profile-photo-frame img")
    page.locator("#identity > .brand-button").click()
    page.wait_for_timeout(150)
    assert page.locator(".brand-profile strong").inner_text() == "Gbedu Studios"
    assert page.locator(".brand-avatar img").count() == 1

    # Every brand route remains usable from laptop to narrow phone.
    for width, height in [(1366, 768), (1024, 768), (820, 1180), (390, 844), (320, 720)]:
        page.set_viewport_size({"width": width, "height": height})
        for name, route in ROUTES:
            page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
            no_overflow(page)
            if width <= 900:
                assert page.locator(".brand-mobile-dock").is_visible(), route
                assert page.locator(".brand-mobile-dock a").count() == 5
                assert not page.locator(".brand-rail").is_visible(), route
            if width <= 390:
                for artwork in page.locator(".brand-art--compact").all():
                    box = artwork.bounding_box()
                    assert box and box["width"] <= 160 and box["height"] <= 165, (route, box)
        if width in {1366, 390, 320}:
            for name, route in [("overview", "/brand"), ("brief", "/brand/campaigns/new/brief"), ("live", "/brand/campaigns/no-long-thing")]:
                page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
                page.wait_for_timeout(500)
                page.screenshot(path=str(OUT / f"responsive-{name}-{width}.png"), full_page=True)

    # Guard the mobile collisions that originally put counters and helper copy
    # on top of campaign fields, and keep the hero scale within the creator UI's range.
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE}/brand/campaigns/new", wait_until="networkidle")
    source_input = page.locator(".brand-input-with-icon input")
    source_help = page.locator(".brand-input-with-icon + small")
    source_box = source_input.bounding_box()
    help_box = source_help.bounding_box()
    assert source_box and help_box
    assert help_box["y"] >= source_box["y"] + source_box["height"], (source_box, help_box)

    page.goto(f"{BASE}/brand", wait_until="networkidle")
    mobile_hero_size = float(
        page.locator(".brand-command h1").evaluate(
            "element => parseFloat(getComputedStyle(element).fontSize)"
        )
    )
    assert mobile_hero_size <= 50, mobile_hero_size

    page.set_viewport_size({"width": 1920, "height": 1080})
    desktop_hero_size = float(
        page.locator(".brand-command h1").evaluate(
            "element => parseFloat(getComputedStyle(element).fontSize)"
        )
    )
    assert desktop_hero_size <= 82, desktop_hero_size

    browser.close()
    assert not errors, errors
    print("PASS: 14 brand surfaces, connected interactions, imagery, and five responsive widths.")
