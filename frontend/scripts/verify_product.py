"""Browser checks for onboarding and the creator product workspace."""

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5174"
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
    assert page.locator("h1").inner_text() == "What should we call you?"
    page.screenshot(path=str(OUT / "01-onboarding-name-desktop.png"), full_page=True)
    page.locator("input[autocomplete=nickname]").fill("Tobi On Cam")
    page.locator(".setup-next").click()
    assert "What do you make for brands?" in page.locator("h1").inner_text()
    page.wait_for_timeout(550)
    page.screenshot(path=str(OUT / "02-onboarding-lanes-desktop.png"), full_page=True)
    page.locator(".setup-next").click()
    assert "Where do you post?" in page.locator("h1").inner_text()
    page.locator(".setup-next").click()
    page.wait_for_url("**/dashboard")

    page.goto(f"{BASE}/onboarding/brand", wait_until="networkidle")
    assert page.locator("h1").inner_text() == "Who is funding the work?"
    page.locator("input[autocomplete=organization]").fill("Gbedu Records")
    page.locator("input[autocomplete=nickname]").fill("Amara")
    page.locator(".setup-next").click()
    assert "What do you want made?" in page.locator("h1").inner_text()
    page.locator(".setup-next").click()
    assert "What should the first campaign move?" in page.locator("h1").inner_text()
    page.wait_for_timeout(550)
    page.screenshot(path=str(OUT / "02b-brand-onboarding-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard", wait_until="networkidle")
    assert page.locator(".studio-nav a.is-active").inner_text() == "Overview"
    assert "₦42,850" in page.locator(".money-total").inner_text()
    assert page.locator(".campaign-vital--rate").is_visible()
    assert page.locator(".campaign-vital--pot").is_visible()
    assert page.locator(".campaign-vital--time").is_visible()
    page.wait_for_timeout(1800)
    page.screenshot(path=str(OUT / "03-dashboard-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard/campaigns", wait_until="networkidle")
    assert page.locator(".campaign-ledger__row").count() == 4
    page.locator(".campaign-search input").fill("Indomie")
    assert page.locator(".campaign-ledger__row").count() == 1
    page.screenshot(path=str(OUT / "04-campaigns-desktop.png"), full_page=True)

    page.goto(
        f"{BASE}/dashboard/campaigns/indomie-no-long-thing",
        wait_until="networkidle",
    )
    page.wait_for_timeout(1500)
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
    assert "Campaign joined" in page.locator(
        ".campaign-detail-hero__action button"
    ).inner_text()
    page.screenshot(path=str(OUT / "05-campaign-detail-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard/leaderboard", wait_until="networkidle")
    assert page.locator(".podium-person").count() == 3
    assert page.locator(".ranking-row:not(.ranking-row--labels)").count() == 6
    page.screenshot(path=str(OUT / "06-leaderboard-desktop.png"), full_page=True)

    page.goto(f"{BASE}/dashboard/settings", wait_until="networkidle")
    assert page.locator(".social-account.is-connected").count() == 2
    page.screenshot(path=str(OUT / "07-settings-desktop.png"), full_page=True)

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE}/onboarding/creator", wait_until="networkidle")
    assert not page.locator(".signal-board").is_visible()
    assert_no_horizontal_overflow(page)
    page.screenshot(path=str(OUT / "08-onboarding-mobile.png"), full_page=True)

    mobile_routes = [
        ("dashboard", "/dashboard"),
        ("campaigns", "/dashboard/campaigns"),
        ("campaign-detail", "/dashboard/campaigns/indomie-no-long-thing"),
        ("leaderboard", "/dashboard/leaderboard"),
        ("settings", "/dashboard/settings"),
    ]
    for name, route in mobile_routes:
        page.goto(f"{BASE}{route}", wait_until="networkidle")
        assert page.locator(".mobile-dock").is_visible()
        assert_no_horizontal_overflow(page)
        if name in ["dashboard", "campaign-detail"]:
            page.screenshot(path=str(OUT / f"09-{name}-viewport.png"))
        page.screenshot(path=str(OUT / f"09-{name}-mobile.png"), full_page=True)

    page.set_viewport_size({"width": 320, "height": 720})
    for route in ["/onboarding/creator", "/onboarding/brand", "/dashboard", "/dashboard/campaigns/indomie-no-long-thing"]:
        page.goto(f"{BASE}{route}", wait_until="networkidle")
        assert_no_horizontal_overflow(page)

    browser.close()
    assert not errors, errors
    print("PASS: onboarding, dashboard, campaigns, detail, leaderboard, settings, and responsive product screens.")
