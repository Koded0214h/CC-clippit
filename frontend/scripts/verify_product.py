"""Browser checks for onboarding and the creator product workspace."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://localhost:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp/qa-product"
OUT.mkdir(parents=True, exist_ok=True)


def assert_no_horizontal_overflow(page):
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto(f"{BASE}/onboarding/creator", wait_until="networkidle")
    assert page.locator("h1").inner_text() == "What would you like to be called?"
    assert page.locator(".typeform-field input").count() == 1
    page.screenshot(path=str(OUT / "01-onboarding-name-desktop.png"), full_page=True)
    page.locator("input[autocomplete=nickname]").fill("Tobi On Cam")
    page.locator(".setup-next").click()
    assert "Where are you creating from?" in page.locator("h1").inner_text()
    assert page.locator(".typeform-field input").count() == 1
    page.locator("input[autocomplete=address-level2]").fill("Lagos, Nigeria")
    page.locator(".setup-next").click()
    assert "What do you like making?" in page.locator("h1").inner_text()
    page.wait_for_timeout(550)
    page.screenshot(path=str(OUT / "02-onboarding-lanes-desktop.png"), full_page=True)
    page.locator(".setup-next").click()
    assert "What stops your scroll?" in page.locator("h1").inner_text()
    page.locator(".setup-next").click()
    assert "Where does your work live?" in page.locator("h1").inner_text()
    page.locator(".setup-next").click()
    assert "How established is your practice?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").nth(2).click()
    page.wait_for_timeout(300)
    assert "How did you hear about us?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").first.click()
    page.wait_for_timeout(300)
    assert "What should Clippit help you do first?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").nth(1).click()
    page.locator(".setup-next").click()
    page.wait_for_url("**/dashboard")

    page.goto(f"{BASE}/onboarding/brand", wait_until="networkidle")
    assert page.locator("h1").inner_text() == "What would you like to be called?"
    page.locator("input[autocomplete=nickname]").fill("Amara")
    page.locator(".setup-next").click()
    assert "Where are you based?" in page.locator("h1").inner_text()
    assert page.locator(".typeform-field input").count() == 1
    page.locator("input[autocomplete=address-level2]").fill("Lagos, Nigeria")
    page.locator(".setup-next").click()
    assert "Are you funding as a brand or an individual?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").first.click()
    page.wait_for_timeout(300)
    assert "Is the company registered?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").first.click()
    page.wait_for_timeout(300)
    assert "What is the organisation called?" in page.locator("h1").inner_text()
    page.locator("input[autocomplete=organization]").fill("Gbedu Records")
    page.locator(".setup-next").click()
    assert "What is your website or social page?" in page.locator("h1").inner_text()
    page.locator("input[autocomplete=url]").fill("https://gbedurecords.example")
    page.locator(".setup-next").click()
    assert "How would you describe it?" in page.locator("h1").inner_text()
    page.locator("textarea").fill("An independent Lagos label building a new home for African pop and its creators.")
    page.locator(".setup-next").click()
    assert "How many people are on the team?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").nth(1).click()
    page.wait_for_timeout(300)
    assert "What kind of content do you want to fund?" in page.locator("h1").inner_text()
    page.locator(".setup-next").click()
    assert "How do you make content now?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").first.click()
    page.wait_for_timeout(300)
    assert "What content do you want to see?" in page.locator("h1").inner_text()
    page.locator(".setup-next").click()
    assert "How did you hear about us?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").first.click()
    page.wait_for_timeout(300)
    assert "What should creators help you achieve?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").nth(2).click()
    page.wait_for_timeout(300)
    assert "What budget range feels right?" in page.locator("h1").inner_text()
    page.locator(".intake-choice-grid button").nth(1).click()
    page.wait_for_timeout(550)
    page.screenshot(path=str(OUT / "02b-brand-onboarding-desktop.png"), full_page=True)
    page.locator(".setup-next").click()
    page.wait_for_url("**/dashboard/campaigns")

    # The individual branch must skip registration, organisation, and workflow.
    page.goto(f"{BASE}/onboarding/brand", wait_until="networkidle")
    page.locator("input[autocomplete=nickname]").fill("Kemi")
    page.locator(".setup-next").click()
    page.locator("input[autocomplete=address-level2]").fill("Abuja, Nigeria")
    page.locator(".setup-next").click()
    page.locator(".intake-choice-grid button").nth(1).click()
    page.wait_for_timeout(300)
    assert "What kind of content do you want to fund?" in page.locator("h1").inner_text()
    assert "Funder setup" in page.locator(".setup-progress").inner_text()

    page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
    assert page.locator(".studio-nav a.is-active").inner_text() == "Overview"
    assert "₦42,850" in page.locator(".money-total").inner_text()
    assert page.locator(".campaign-vital--rate").is_visible()
    assert page.locator(".campaign-vital--pot").is_visible()
    assert page.locator(".campaign-vital--time").is_visible()
    assert page.locator(".creator-reel__card").count() == 4
    assert page.locator(".creator-reel video").count() == 1
    page.wait_for_timeout(1800)
    page.screenshot(path=str(OUT / "03-dashboard-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard/campaigns", wait_until="domcontentloaded")
    page.wait_for_timeout(650)
    assert page.locator(".campaign-ledger__row").count() == 4
    page.locator(".campaign-search input").fill("Indomie")
    assert page.locator(".campaign-ledger__row").count() == 1
    page.screenshot(path=str(OUT / "04-campaigns-desktop.png"), full_page=True)

    page.goto(
        f"{BASE}/dashboard/campaigns/indomie-no-long-thing",
        wait_until="domcontentloaded",
    )
    page.wait_for_function(
        "document.querySelector('.campaign-vital--pot strong')?.textContent?.includes('312,500')",
        timeout=10000,
    )
    detail_text = page.locator(".campaign-detail-page").inner_text()
    for required in [
        "₦500",
        "₦312,500",
        "Starts earning at",
        "Holding period",
        "Full thousands only",
        "Your clip must",
    ]:
        assert required in detail_text
    assert page.locator(".payment-math").count() == 0
    assert page.locator(".campaign-vitals--detail").is_visible()
    page.locator(".campaign-detail-hero__action button").click()
    assert "Submit your clip" in page.locator(
        ".campaign-detail-hero__action a"
    ).inner_text()
    page.screenshot(path=str(OUT / "05-campaign-detail-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard/leaderboard", wait_until="domcontentloaded")
    assert page.locator(".podium-person").count() == 3
    assert page.locator(".ranking-row:not(.ranking-row--labels)").count() == 6
    page.screenshot(path=str(OUT / "06-leaderboard-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard/settings", wait_until="domcontentloaded")
    assert page.locator(".social-account.is-connected").count() == 2
    page.wait_for_timeout(500)
    page.locator('.settings-index a[href="#accounts"]').click()
    assert "Social accounts" in page.locator(".settings-index a.is-active").inner_text()
    page.screenshot(path=str(OUT / "07-settings-desktop.png"), full_page=True)

    # Laptop and tablet widths used to inherit desktop minimums and overflow.
    responsive_routes = [
        "/onboarding/creator",
        "/onboarding/brand",
        "/dashboard",
        "/dashboard/campaigns",
        "/dashboard/campaigns/indomie-no-long-thing",
        "/dashboard/leaderboard",
        "/dashboard/settings",
    ]
    for width, height in [(1366, 768), (1024, 768), (820, 1180)]:
        page.set_viewport_size({"width": width, "height": height})
        for route in responsive_routes:
            page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
            assert_no_horizontal_overflow(page)
        if width == 1366:
            page.goto(f"{BASE}/onboarding/creator", wait_until="domcontentloaded")
            page.wait_for_timeout(600)
            page.screenshot(path=str(OUT / "08-onboarding-1366.png"), full_page=True)
        page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
        if width > 900:
            assert page.locator(".studio-rail").is_visible()
            assert not page.locator(".mobile-dock").is_visible()
        else:
            assert not page.locator(".studio-rail").is_visible()
            assert page.locator(".mobile-dock").is_visible()
        page.screenshot(path=str(OUT / f"08-dashboard-{width}.png"), full_page=True)

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE}/onboarding/creator", wait_until="domcontentloaded")
    assert not page.locator(".signal-board").is_visible()
    assert_no_horizontal_overflow(page)
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "08-onboarding-mobile.png"), full_page=True)

    mobile_routes = [
        ("dashboard", "/dashboard"),
        ("campaigns", "/dashboard/campaigns"),
        ("campaign-detail", "/dashboard/campaigns/indomie-no-long-thing"),
        ("leaderboard", "/dashboard/leaderboard"),
        ("settings", "/dashboard/settings"),
    ]
    for name, route in mobile_routes:
        page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
        assert page.locator(".mobile-dock").is_visible()
        assert_no_horizontal_overflow(page)
        if name in ["dashboard", "campaign-detail"]:
            page.screenshot(path=str(OUT / f"09-{name}-viewport.png"))
        page.screenshot(path=str(OUT / f"09-{name}-mobile.png"), full_page=True)

    page.set_viewport_size({"width": 320, "height": 720})
    for route in ["/onboarding/creator", "/onboarding/brand", "/dashboard", "/dashboard/campaigns/indomie-no-long-thing"]:
        page.goto(f"{BASE}{route}", wait_until="domcontentloaded")
        assert_no_horizontal_overflow(page)

    browser.close()
    assert not errors, errors
    print("PASS: onboarding, dashboard, campaigns, detail, leaderboard, settings, and responsive product screens.")
