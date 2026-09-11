# Clippit

A bright creator-first landing page: social collages, campaign posters, an interactive earnings calculator, a brand brief builder, and the original phone-throw finale.

## Run locally

```sh
python serve.py
```

Open http://localhost:5174. No dependencies or build step are needed to serve the page. The development server disables caching.

## Files

- `index.html`: page content and accessible SVG icons.
- `styles.css`: design tokens, responsive compositions, and entrance animations.
- `main.js`: campaign filters, calculator, accessible dialogs, downloadable brief, finite confetti, and scroll-driven phone throw.
- `assets/photos/`: locally downloaded photography; credits are linked in the website footer.
- `assets/throw/`: the existing 84-frame sequence and its final phone geometry.
- `DESIGN-NOTES.md`: art direction, reference links, asset provenance, and implementation scope.

## Working interactions

- Filter the three illustrative campaign previews by category.
- Open a brief, read its sample requirements, and try its rate in the calculator.
- Calculate example earnings at three campaign rates. Only full thousands count.
- Create a sample brand brief and download it as a text file. Nothing is published or charged.
- Expand the FAQs, use the mobile menu, and open photography credits.
- Scroll through the retained phone throw, skip it, or replay confetti at the finale.

All sections use light backgrounds. The skating character and ink-reveal implementation have been removed; existing unused character files remain on disk. Reduced-motion preferences produce a static closing section. Primary content remains readable without JavaScript.

## Scope

This is a landing page with functional local previews. Campaigns, views, and earnings are illustrative, not live offers or customer testimonials. Real accounts, platform connections, escrow funding, submissions, and withdrawals require backend integration.

## Backend services

Additional services are available under `backend/service-test/`:

- **`meta_insta/`**: Flask app for Instagram Business account metrics via OAuth. Connect an Instagram Creator/Business account and view profile data, posts, engagement metrics (views, reach, saved, likes, comments), and account-level insights.

Each service has its own setup instructions in its `README.md`.

## Browser verification

With Python Playwright and its Chromium browser installed:

```sh
python -X utf8 -u scripts/verify.py
```

The script verifies the main interactions, desktop/mobile layouts, reduced motion, and no-JavaScript content, and saves visual captures in `tmp/qa/`.
