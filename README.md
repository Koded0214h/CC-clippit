# Clippit

Clippit is a creator campaign product for the Nigerian market: creators discover funded briefs, submit social clips, earn from verified views, and withdraw cleared naira earnings. Organisations fund campaigns and track attention against their budgets.

## Repository

- `frontend/` — Next.js 16, React 19, and strict TypeScript
- `backend/service-test/` — isolated Python service experiments for social-platform integrations
- `frontend/public/assets/` — local brand, photography, video, and motion assets

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5174`. The server listens on all network interfaces, so another device on the same Wi-Fi can open `http://<your-ip>:5174`.

For a production build:

```powershell
npm run typecheck
npm run lint
npm run build
npm run start
```

The marketing page lives at `/`. Authentication uses real routes under `/auth`, beginning with `/auth/sign-up` and `/auth/sign-in`.

## Current scope

The frontend implements the full reviewable UX for landing, registration, sign in, email verification, password recovery, OTP entry, and password reset. Campaign offers, balances, and earnings remain clearly illustrative until production APIs connect identity, platform verification, escrow, and payouts.

See [`frontend/README.md`](frontend/README.md) for route details, architecture, and verification commands.
