# Clippit — creator collage redesign

## Direction

An oversized typographic poster beside social cards, annotated with handwritten notes, a lime orbit, a payday receipt, and a smiley stamp. The visual language continues through miniature product demonstrations, campaign artwork, a calculator receipt, and a creator-powered brand campaign board.

The supplied design system informs the lime actions (`#B8FF38`), gold money (`#EFC884`), paper (`#F7F8F2`), white surfaces, and Geist/Kalam pairing. The user's instruction overrides the original dark-surface direction: all page sections, navigation, footer, and the phone-throw stage are light.

The first typography plan used marker lettering throughout. The final design uses oversized Geist for the main hierarchy and Kalam for handwritten annotations, preserving their contrast and keeping dense product details readable.

## References and assets

- [TryShoot](https://tryshoot.com/) informed the creator-first presentation, prominent social content, and visible posting-to-payout loop. Its business claims and payout rules were not copied.
- `Clippit_Design_System.pdf` and `clipit-prd.pdf`, supplied by the user, informed the palette, product logic, and copy.
- The supplied September 8 brand image informed the italic wordmark treatment, underlines, and marker annotations. Existing logo assets are retained.
- [Lagos portrait — Prince Akachi](https://unsplash.com/photos/smiling-woman-wearing-turban-i2hoD-C2RUA): `assets/photos/lagos-portrait.jpg`.
- [Sunglasses portrait — Alex Robinson](https://unsplash.com/photos/woman-wearing-white-blouse-and-black-cateye-sunglasses-4ar-CSxLcMg): `assets/photos/fashion.jpg`.
- [Afro and sunglasses — Divaris Shirichena](https://unsplash.com/photos/stylish-woman-with-afro-hair-wearing-sunglasses-and-red-shirt-g95oS2hb7Rg): `assets/photos/afro-style.jpg`.
- [Street-style headphones portrait](https://unsplash.com/photos/a-man-standing-on-a-sidewalk-wearing-headphones-fvHrDsKR0Gc): `assets/photos/street-style.jpg`.

Photography is stored locally. Photo credits are accessible from the footer. People pictured are models, not claimed Clippit customers or endorsers. Social cards are original HTML/CSS mockups; their labels disclose illustrative views and earnings. A direct TikTok profile screenshot was attempted, but the page did not finish loading useful content, so that screenshot is not used in the website.

## Motion

- Headline lines enter in sequence, social cards toss into place, then the receipt and stamp arrive.
- Section compositions reveal once, using IntersectionObserver. The chart grows with its board.
- Finite canvas confetti plays at the opening and finale; the finale has a replay button.
- The original 84-frame phone throw is preserved and loaded near its section. A matching DOM phone grows from the final frame into the closing CTA. Scrolling can reverse the sequence. A skip control is included.
- The old skating character, pole, and ink-mask sections are removed from the implementation. Their existing image files are left on disk.
- Reduced-motion preferences disable decorative motion and replace the phone sequence with a static, accessible closing section.

## Product scope

This remains a standalone landing page, not an implemented creator marketplace. Campaign cards and earnings are labelled previews. The calculator applies full thousands and discloses the 1,000-view minimum, campaign caps, available budget, and five-day hold. The brand builder downloads a local plain-text brief; it does not publish, store personal data, or take payment. Account connections, real campaign data, escrow, and withdrawals still require the application backend.

## Verification

`scripts/verify.py` exercises the landing page with a headless Chromium browser. It checks campaign filtering, brief dialogs, calculator values including zero and maximum, sample brief download, mobile navigation, the phone finale, reduced motion, and readable content with JavaScript disabled. Screenshots are saved under `tmp/qa/` for visual review.

The in-app browser connection returned a sandbox metadata error, so local visual QA uses headless Playwright.
