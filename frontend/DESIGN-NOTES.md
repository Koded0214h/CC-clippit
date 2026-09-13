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
- Each card type has its own entrance: the brief slides and tilts into place, the photo swings from its top edge, checklist rows and ticks arrive sequentially, and the payout receipt feeds down and unfolds. Campaign posters land with a small overshoot, followed by artwork, category badges, rates, and budget bars.
- The calculator unfolds its gold receipt, the verification board assembles its rows before the stamp lands, and the brand chart grows bar by bar before its creator avatars pop in. Social UI and view badges arrive after the hero cards settle.
- IntersectionObserver triggers each composition once. Only siblings entering together are staggered, so a lone mobile card starts immediately. Filtered cards receive a fresh entrance when returned. Finished animations release their styles, keyboard focus settles a card immediately, and changing reduced-motion preferences cancels active entrances.
- Finite canvas confetti plays at the opening and finale; the finale has a replay button.
- The original 84-frame phone throw is preserved and loaded near its section. A matching DOM phone grows from the final frame into the closing CTA. Scrolling can reverse the sequence; the old skip control has been removed.
- The old skating character, pole, and ink-mask sections are removed from the implementation. Their existing image files are left on disk.
- Reduced-motion preferences disable decorative motion and replace the phone sequence with a static, accessible closing section.

## Product scope

The marketing surface and authentication journey now run as one Next.js application. Campaign cards and earnings remain labelled previews. The calculator applies full thousands and discloses the 1,000-view minimum, campaign caps, available budget, and five-day hold. The brand builder downloads a local plain-text brief; it does not publish, store personal data, or take payment. Account connections, real campaign data, escrow, and withdrawals still require the application backend.

## Authentication flow

The auth journey uses proper App Router paths under `/auth`, with a shared React shell, typed flow state, reusable form primitives, and one page per authentication state. It keeps the same paper, lime, gold, ink, Geist, and Kalam system beside a disciplined form workspace.

The frontend covers account-type selection, creator and organisation registration, sign in, email verification, password recovery, recovery OTP, new password, and completion states. Forms include inline validation, password visibility controls, keyboard-friendly OTP entry and paste, resend cooldown feedback, reduced-motion behavior, and layouts down to 320px. Identity persistence, mail delivery, sessions, and OAuth remain ready for production API integration rather than being simulated with local storage.

The final auth treatment keeps a single creator video as a desktop-only atmosphere layer. All editorial copy and status chrome were removed from the footage; the only story beat is an animated comic notification from the creator's phone: “You just received ₦55,000 for your Indomie content.” Mobile omits the video scene entirely so the task starts immediately. The footage is the commercial-use Mixkit clip [Happy man chatting on his cell phone](https://mixkit.co/free-stock-video/happy-man-chatting-on-his-cell-phone-41167/) under the Mixkit Stock Video Free License. It is illustrative stock footage; the person shown is not presented as a Clippit customer or endorser.

## Verification

`scripts/verify.py` exercises the landing page with a headless Chromium browser. It checks campaign filtering, brief dialogs, calculator values including zero and maximum, sample brief download, mobile navigation, the phone finale, reduced motion, and readable content with JavaScript disabled. Screenshots are saved under `tmp/qa/` for visual review.

The in-app browser connection returned a sandbox metadata error, so local visual QA uses headless Playwright.
