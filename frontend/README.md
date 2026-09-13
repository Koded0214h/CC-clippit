# Clippit web app

The Clippit frontend is a production-oriented Next.js application using the App Router, React, and strict TypeScript. It contains the creator-first marketing site and the complete authentication journey.

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

- `/` — marketing site and interactive product previews
- `/auth/sign-up` — account type
- `/auth/sign-up/creator` — creator registration
- `/auth/sign-up/organisation` — organisation registration
- `/auth/sign-in` — sign in
- `/auth/forgot-password` — recovery email
- `/auth/recovery-code` — recovery OTP
- `/auth/reset-password` — new password
- `/auth/verify-email` — registration OTP
- `/auth/success` — completion state

## Structure

- `app/` — App Router pages, layouts, metadata, and global foundations
- `components/auth/` — typed auth flow, shell, forms, and OTP behavior
- `components/landing/` — landing-page composition
- `components/ui/` — shared brand and icon primitives
- `lib/` — shared route metadata, types, and validation rules
- `styles/` — the Clippit landing and auth visual systems
- `public/assets/` — local images, video, and phone-throw frames
- `scripts/` — Playwright browser verification

The forms are ready for a production identity API. They deliberately do not fake sessions, mail delivery, payments, or account persistence in browser storage.

## Verification

Run the production server, then:

```powershell
python -X utf8 -u scripts/verify.py
python -X utf8 -u scripts/verify_auth.py
```

These checks cover landing interactions, routed auth flows, validation, OTP entry, password recovery, reduced motion, no-JavaScript rendering, and responsive widths from 320px to 1920px.
