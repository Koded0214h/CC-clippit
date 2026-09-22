from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:5174"
ROUTES = [
    "/dashboard/verification/status",
    "/brand",
    "/brand/campaigns",
    "/brand/campaigns/no-long-thing",
    "/brand/campaigns/campus-chop/report",
    "/brand/campaigns/campus-chop/refund",
    "/brand/campaigns/new",
    "/brand/campaigns/new/brief",
    "/brand/campaigns/new/platforms",
    "/brand/campaigns/new/rules",
    "/brand/campaigns/new/budget",
    "/brand/campaigns/new/review",
    "/brand/campaigns/new/fund",
    "/brand/campaigns/new/funded",
    "/brand/notifications",
    "/brand/reviews",
    "/brand/reviews/submission-1042",
    "/brand/settings",
    "/brand/team",
    "/brand/team/invite",
    "/brand/billing",
    "/brand/invoices/INV-0926-041",
    "/brand/transactions",
    "/brand/transactions/FEE-00419",
    "/brand/verification",
    "/brand/verification/business",
    "/brand/verification/documents",
    "/brand/verification/status",
]


def audit_page(page, route: str, width: int, height: int) -> None:
    response = page.goto(f"{BASE_URL}{route}", wait_until="networkidle")
    assert response and response.ok, f"{route} returned {response.status if response else 'no response'}"
    assert page.locator("main").count(), f"{route} did not render the app shell"
    assert not page.get_by_text("Application error", exact=False).count(), f"{route} rendered an application error"
    visible_copy = page.locator("body").inner_text()
    for internal_term in ("KYC", "KYB", "Paystack costs", "provider fee"):
        assert internal_term not in visible_copy, f"{route} exposes internal cost language: {internal_term}"

    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
    assert not overflow, f"{route} overflows horizontally at {width}px"

    clipped = page.locator(".brand-status, .completion-status").evaluate_all(
        """els => els.map(el => ({
          text: el.textContent.trim(),
          clipped: el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1
        })).filter(item => item.clipped)"""
    )
    assert not clipped, f"{route} has clipped status tags at {width}px: {clipped}"

    broken_brand_tags = page.locator(".brand-status").evaluate_all(
        """els => els.map(el => {
          const dot = el.querySelector('.brand-status__dot');
          const textNode = [...el.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
          let textRect = null;
          if (textNode) {
            const range = document.createRange();
            range.selectNodeContents(textNode);
            textRect = range.getBoundingClientRect();
          }
          const dotRect = dot?.getBoundingClientRect();
          return {
            text: el.textContent.trim(),
            display: getComputedStyle(el).display,
            overlap: Boolean(dotRect && textRect && dotRect.right > textRect.left + 0.5)
          };
        }).filter(item => item.display !== 'none' && (!['inline-flex', 'flex'].includes(item.display) || item.overlap))"""
    )
    assert not broken_brand_tags, f"{route} has malformed brand tags at {width}px: {broken_brand_tags}"

    orbit = page.locator(".status-orbit")
    if orbit.count():
        collision = orbit.evaluate(
            """el => {
              const title = el.querySelector(':scope > strong')?.getBoundingClientRect();
              const timestamp = el.querySelector(':scope > small')?.getBoundingClientRect();
              const rings = [...el.querySelectorAll(':scope > i')]
                .map(ring => ring.getBoundingClientRect());
              return Boolean(title && timestamp && (
                title.bottom > timestamp.top + 0.5 ||
                rings.some(ring => ring.bottom > title.top + 0.5)
              ));
            }"""
        )
        assert not collision, f"{route} has a verification orbit/text collision at {width}px"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    for route in ROUTES:
        audit_page(page, route, 1440, 1000)

    page.set_viewport_size({"width": 390, "height": 844})
    for route in ROUTES:
        audit_page(page, route, 390, 844)

    page.goto(f"{BASE_URL}/brand/team/invite", wait_until="networkidle")
    page.locator('input[type="email"]').fill("newmember@gbedurecords.com")
    page.get_by_text("Reviewer", exact=True).click()
    page.get_by_role("button", name="Send invitation").click()
    page.get_by_role("heading", name="Invitation sent").wait_for()
    page.wait_for_function("window.scrollY === 0")
    assert page.get_by_text("Sent successfully", exact=True).is_visible()
    assert page.get_by_text("newmember@gbedurecords.com", exact=True).is_visible()
    assert page.get_by_text("They can join Gbedu Records as a Reviewer.", exact=True).is_visible()
    page.screenshot(path="tmp/qa-completion/brand-invite-success-mobile.png", full_page=True)

    page.goto(f"{BASE_URL}/brand", wait_until="networkidle")
    page.get_by_role("button", name="More").click()
    page.get_by_role("link", name="Billing").wait_for()
    assert page.get_by_role("link", name="Verification").is_visible()
    page.screenshot(path="tmp/qa-completion/brand-more-menu-mobile.png")
    page.get_by_role("link", name="Verification").click()
    page.wait_for_url(f"{BASE_URL}/brand/verification")
    page.get_by_role("heading", name="Verify Gbedu Records").wait_for()
    page.wait_for_timeout(300)
    assert page.locator(".brand-mobile-more").get_attribute("aria-hidden") == "true"
    page.screenshot(path="tmp/qa-completion/brand-verification-start-mobile.png", full_page=True)

    page.goto(f"{BASE_URL}/brand/billing", wait_until="networkidle")
    page.get_by_role("button", name="Edit billing details").click()
    page.get_by_role("heading", name="Edit billing details").wait_for()
    page.screenshot(path="tmp/qa-completion/brand-billing-editor-mobile.png", full_page=True)
    page.get_by_label("Legal business name").fill("Gbedu Records and Media Limited")
    page.get_by_role("button", name="Save changes").click()
    page.get_by_text("Billing details updated", exact=True).wait_for()
    page.locator(".invoice-stack > a").last.scroll_into_view_if_needed()
    assert page.locator(".invoice-stack > a").last.is_visible()
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(100)
    page.screenshot(path="tmp/qa-completion/brand-billing-mobile.png", full_page=True)

    for route, filename in [
        ("/dashboard/verification/status", "creator-verification-spacing-mobile.png"),
        ("/brand/verification/status", "brand-verification-spacing-mobile.png"),
    ]:
        page.goto(f"{BASE_URL}{route}", wait_until="networkidle")
        page.screenshot(path=f"tmp/qa-completion/{filename}", full_page=True)

    page.goto(f"{BASE_URL}/brand/campaigns/new/fund", wait_until="networkidle")
    page.get_by_text("Clippit campaign fee (15%)", exact=True).wait_for()
    assert page.locator('.animated-number[aria-label="₦75,000"]').count()
    assert page.locator('.animated-number[aria-label="₦575,000"]').count()

    page.goto(f"{BASE_URL}/dashboard/withdraw", wait_until="networkidle")
    page.get_by_text("Clippit fee (7%)", exact=True).wait_for()
    assert page.locator('.animated-number[aria-label="₦1,288"]').count()
    assert page.locator('.animated-number[aria-label="₦17,112"]').count()

    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{BASE_URL}/brand/settings", wait_until="networkidle")
    page.screenshot(path="tmp/qa-completion/brand-settings-badges-fixed.png", full_page=True)
    page.goto(f"{BASE_URL}/brand/verification/status", wait_until="networkidle")
    page.screenshot(path="tmp/qa-completion/brand-verification-spacing-fixed.png", full_page=True)
    browser.close()

print(f"Verified {len(ROUTES)} brand and verification routes at desktop and mobile widths, including invite, billing edit, and mobile verification access.")
