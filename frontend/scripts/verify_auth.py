"""Browser checks for the routed authentication flow."""

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5174/auth"
OUT = Path(__file__).resolve().parents[1] / "tmp/qa-auth"
OUT.mkdir(parents=True, exist_ok=True)


def fill_code(page):
    for index, digit in enumerate("246810"):
        page.locator("[data-otp] input").nth(index).fill(digit)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    page.goto(f"{BASE}/sign-up", wait_until="domcontentloaded")
    page.wait_for_selector("#roleForm")
    assert page.locator(".auth-story").is_visible()
    page.screenshot(path=str(OUT / "desktop-sign-up.png"), full_page=True)
    page.wait_for_timeout(3800)
    assert page.locator(".comic-payment").evaluate(
        "element => Number(getComputedStyle(element).opacity) > 0.8"
    )
    page.screenshot(path=str(OUT / "desktop-payment.png"), full_page=True)

    page.locator("input[value=creator]").check()
    page.locator("#roleForm button").click()
    page.wait_for_url("**/auth/sign-up/creator")
    assert page.locator('[data-google-auth="signup"]').is_visible()
    page.locator("#creatorForm button[type=submit]").click()
    assert page.locator("#creatorForm .has-error").count() == 4
    page.locator("input[name=firstName]").fill("Tomi")
    page.locator("input[name=lastName]").fill("Adeyemi")
    page.locator("input[name=email]").fill("tomi@example.com")
    page.locator("input[name=password]").fill("clippit2026")
    page.locator("#creatorForm button[type=submit]").click()
    page.wait_for_url("**/auth/verify-email")
    assert "tomi@example.com" in page.locator(".auth-intro").inner_text()
    fill_code(page)
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/auth/success")

    page.goto(f"{BASE}/sign-in", wait_until="domcontentloaded")
    assert page.locator('[data-google-auth="signin"]').is_visible()
    page.locator("#signinForm button[type=submit]").click()
    assert page.locator("#signinForm .has-error").count() == 2
    page.locator("input[name=email]").fill("tomi@example.com")
    page.locator("input[name=password]").fill("clippit2026")
    page.locator("#signinForm button[type=submit]").click()
    page.wait_for_url("**/auth/success")

    page.goto(f"{BASE}/forgot-password", wait_until="domcontentloaded")
    page.locator("input[name=email]").fill("tomi@example.com")
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/auth/recovery-code")
    fill_code(page)
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/auth/reset-password")
    page.locator("input[name=password]").fill("newclippit2026")
    page.locator("input[name=confirmPassword]").fill("newclippit2026")
    assert page.locator(".password-rules .is-met").count() == 2
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/auth/success")

    for width, height in [(390, 844), (768, 1024), (1024, 800), (1920, 1080), (320, 720)]:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{BASE}/sign-up/creator", wait_until="domcontentloaded")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        if width <= 768:
            assert not page.locator(".auth-story").is_visible()
        page.screenshot(path=str(OUT / f"responsive-{width}.png"), full_page=True)

    no_js = browser.new_page(
        viewport={"width": 390, "height": 844}, java_script_enabled=False
    )
    no_js.goto(f"{BASE}/sign-up", wait_until="domcontentloaded")
    assert no_js.locator("h1").is_visible()
    no_js.close()

    browser.close()
    assert not errors, errors
    print("PASS: routed sign-up, sign-in, recovery, OTP, responsive, and no-JS auth screens.")
