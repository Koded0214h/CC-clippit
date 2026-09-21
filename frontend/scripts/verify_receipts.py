"""Render the receipt print views and verify their one-page output."""

import os
from pathlib import Path

import fitz
from playwright.sync_api import sync_playwright

BASE = os.getenv("CLIPPIT_BASE", "http://localhost:5174")
OUT = Path(__file__).resolve().parents[1] / "tmp" / "qa-receipts"
OUT.mkdir(parents=True, exist_ok=True)

RECEIPTS = [
    ("creator", "/dashboard/payouts/receipt", "₦18,400", "Official payout receipt"),
    ("brand", "/brand/transactions/CLP-0926-041", "₦525,000", "Official transaction receipt"),
    ("brand-list", "/brand/transactions", "₦525,000", "Official transaction receipt"),
]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 960})

    for name, route, amount, title in RECEIPTS:
        response = page.goto(f"{BASE}{route}", wait_until="networkidle")
        assert response and response.ok, route
        page.wait_for_selector("[data-receipt-watermark] img", state="attached")
        assert page.locator("[data-receipt-watermark] img").count() == 12, name
        assert page.locator("[data-receipt-watermark] img").first.get_attribute("loading") != "lazy", name
        page.emulate_media(media="print")
        pdf_path = OUT / f"{name}-receipt.pdf"
        page.pdf(
            path=str(pdf_path),
            print_background=True,
            prefer_css_page_size=True,
        )

        document = fitz.open(pdf_path)
        assert document.page_count == 1, (name, document.page_count)
        assert len(document[0].get_image_info()) >= 14, (name, "watermark images missing")
        receipt_text = "\n".join(pdf_page.get_text() for pdf_page in document)
        assert amount in receipt_text, (name, amount, receipt_text)
        assert title in receipt_text, (name, title)
        first_page = document[0].get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
        first_page.save(OUT / f"{name}-receipt.png")
        document.close()
        page.emulate_media(media="screen")

    browser.close()

print("PASS: creator and brand receipts render as complete single-page PDFs.")
