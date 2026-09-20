# Clippit web app

The Clippit frontend is a production-oriented Next.js application using the App Router, React, and strict TypeScript. It contains the creator-first marketing site, authentication journey, onboarding flow, and creator campaign workspace.

## Requirements

- Node.js 20.9 or newer
- npm 10 or newer

## Local development

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5174`. The development server binds to `0.0.0.0`, so phones and computers on the same Wi-Fi can use `http://<your-ip>:5174`.

## Production check

```powershell
npm run typecheck
npm run lint
npm run build
npm run start
```

## Routes

- `/` - marketing site and interactive product previews
- `/auth/sign-up` - account type
- `/auth/sign-up/creator` - creator registration
- `/auth/sign-up/organisation` - organisation registration
- `/auth/sign-in` - sign in
- `/auth/forgot-password` - recovery email
- `/auth/recovery-code` - recovery OTP
- `/auth/reset-password` - new password
- `/auth/verify-email` - registration OTP
- `/auth/success` - completion state
- `/onboarding/creator` - creator name, content lanes, and social platforms
- `/onboarding/brand` - organisation identity, desired content, and campaign goal
- `/dashboard` - creator overview, campaign activity, and earnings
- `/dashboard/campaigns` - searchable funded campaign feed
- `/dashboard/campaigns/[slug]` - campaign brief, timing, rules, and payment logic
- `/dashboard/leaderboard` - verified-view rankings
- `/dashboard/settings` - profile, socials, payout account, and notifications
- `/brand` - funded-attention overview and live campaign signals
- `/brand/campaigns` - brand campaign portfolio
- `/brand/campaigns/new/*` - interactive campaign, brief, platform, rule, budget, review, and funding studio
- `/brand/campaigns/[slug]` - live pot, verified views, submission flow, and creator earnings
- `/brand/reviews` - uncertain-submission review queue
- `/brand/reviews/[id]` - evidence-led human approval or correction decision
- `/brand/settings` - organisation identity, funding contact, and campaign alerts

## Structure

- `app/` - App Router pages, layouts, metadata, and global foundations
- `components/auth/` - typed auth flow, shell, forms, and OTP behavior
- `components/onboarding/` - responsive account setup flow
- `components/dashboard/` - product shell and campaign workspace screens
- `components/brand/` - brand control room, campaign builder, funding, and review workspace
- `components/landing/` - landing-page composition
- `components/ui/` - shared brand and SVG icon primitives
- `lib/` - shared route metadata, product data, types, and validation rules
- `styles/` - the Clippit landing, auth, onboarding, and product visual systems
- `public/assets/` - local images, video, and phone-throw frames
- `scripts/` - Playwright browser verification

The prototype forms and product actions are ready for production APIs. They deliberately do not fake sessions, mail delivery, payments, social connections, or account persistence in browser storage.

## Verification

Run the production server, then:

```powershell
python -X utf8 -u scripts/verify.py
python -X utf8 -u scripts/verify_auth.py
python -X utf8 -u scripts/verify_product.py
```

These checks cover landing interactions, routed auth flows, onboarding, campaign search and joining, campaign-detail requirements, leaderboards, settings, fixed mobile navigation, validation, OTP entry, password recovery, reduced motion, no-JavaScript rendering, and responsive widths from 320px to 1920px.
