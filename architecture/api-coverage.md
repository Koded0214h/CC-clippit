# API coverage — what the screens need vs what the backend serves

Snapshot of 2026-09-21 — **built**: 84 API paths, ~390 tests, and every row
below marked 🆕/🔒/⚠️ now has its endpoint. Method: every route under `frontend/app/` and the
components behind it were read for the data they show and the actions they
take; each need was matched to a backend route. The frontend currently runs
on hard-coded fixtures (`lib/product.ts`, `lib/brand.ts`, component state and
`localStorage`), so "needs" below are inferred from those fixtures.

Legend: ✅ served before this pass · 🆕 built in this pass · ⚠️ served but the
shape needed changing · 🔒 built behind a provider abstraction (sandbox until a
real provider is chosen)

## Auth & onboarding

| Screen | Needs | Status |
|---|---|---|
| `/auth/sign-up/*`, `/auth/sign-in` | signup, login | ✅ |
| `/auth/verify-email` (OTP + "send a new code") | verify code, resend with cooldown, `email_verified` on user | 🆕 `POST /auth/verify-email`, `POST /auth/verify-email/resend` |
| `/auth/forgot-password` → `recovery-code` → `reset-password` | request code, check code, set new password | 🆕 `POST /auth/forgot-password`, `POST /auth/recovery-code/verify`, `POST /auth/reset-password` |
| logout | revoke token | ✅ |
| `/onboarding/creator` | name, lanes (interests), platforms, discovery, experience, goals, photo | 🆕 `PUT /creators/me/onboarding` |
| `/onboarding/brand` | org name, workflow, team size, campaign goal, budget, description, photo | 🆕 `PUT /organisations/me/onboarding` |
| photo pickers | image upload | 🆕 `POST /uploads/images` |

## Creator workspace (`/dashboard/*`)

| Screen | Needs | Status |
|---|---|---|
| Home | featured/closing campaign, new matches, earnings summary | 🆕 `GET /creators/me/overview` (also `GET /earnings/summary`) |
| Campaign feed | search, category/status filters, "Joined", time left, pot remaining, brand name, cover | ⚠️ `GET /campaigns` gains `q`, `category`, `platform`, `feed` filters and card fields |
| Campaign detail | brief, must-do / must-avoid, min views, creator cap, platforms | ⚠️ campaign gains brief rules; 🆕 `GET/PUT /campaigns/{id}/rules`; ids accept slug |
| Connected accounts | list with handle, connect/disconnect, last checked | ⚠️ social accounts gain `handle`, `display_name`, `last_checked_at` |
| Submit clip (platform, link, **original video file**) | validate + register, file upload | ⚠️ `POST /submissions` gains `title`, `video_upload_id`; 🆕 `POST /uploads/videos` |
| Processing screen (post ownership → brief → trust → first reading) | live verdict progress | 🆕 `GET /submissions/{id}` carries `verification` steps |
| Approved / Rejected verdict | per-requirement results, failed requirement + reason, accrued so far, payable date | 🆕 `verification.requirements[]`, `GET /submissions/{id}/earnings` |
| Appeal | reason (≥20), optional evidence | 🆕 `POST /submissions/{id}/appeal` |
| My clips | totals + rows (status, verified views, earned) | 🆕 `GET /creators/me/clips` |
| Earnings | payable / in hold / paid / lifetime views, hold timeline, history | 🆕 `GET /earnings/summary`, `GET /earnings/history` |
| Withdraw | amount ≥ ₦1,000, verified destination, fee, confirm | 🔒 `POST /payouts` |
| Payout receipt | reference, status, destination, provenance | 🔒 `GET /payouts/{id}` |
| Leaderboard | weekly ranking by verified views | 🆕 `GET /leaderboard` |
| Settings — profile | name, bio, photo | 🆕 `GET/PUT /creators/me/profile` |
| Settings — payout account | bank + verified name | ✅ set/get · 🔒 `GET /banks`, `POST /creators/me/bank-details/verify` |
| Settings — notifications | four toggles | ⚠️ preferences gain `notifications` |
| Shell — bell | in-app inbox | 🆕 `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |

## Brand workspace (`/brand/*`)

| Screen | Needs | Status |
|---|---|---|
| Overview | pending reviews, live campaign, verified views today, earnings today, unmatched spend | 🆕 `GET /brand/overview` |
| Campaigns list | state Live/Draft/Completed/Funding, pot, remaining, verified views, clips, approved, review, days left, cover | ⚠️ `GET /campaigns` (organisation) carries a `metrics` block |
| Builder — details / brief / platforms / rules / budget | title, description, source link, must/avoid rules, platforms, min views, creator cap, days, pot, rate | ⚠️ campaign gains `tagline`, `source_link`, `category`, `cover_image_url`, `duration_days`, `pot`; 🆕 `/campaigns/{id}/rules` |
| Review → Fund | funding order: reference, pot, fee (1.5%), total, method, collection account | 🔒 `POST /campaigns/{id}/funding`, `GET /campaigns/{id}/funding` |
| "I have funded the pot" → Funded | confirm, certificate, provider reference | 🔒 `POST /campaigns/{id}/funding/confirm`, `POST /webhooks/payments` |
| Live campaign | pause/resume entries, pot bar, verified views (+delta), pipeline counts, last platform reading, recent submissions, export | 🆕 `POST /campaigns/{id}/pause`, `/resume`, `GET /campaigns/{id}/stats`, `GET /campaigns/{id}/submissions`, `GET /campaigns/{id}/report` |
| Review queue (Needs review / Appeals / Resolved) | queue with confidence, issue, age | 🆕 `GET /brand/reviews` |
| Review detail | requirements with pass/review, decision | 🆕 `GET /brand/reviews/{id}`, `POST …/approve`, `POST …/request-correction` |
| Settings | org identity, finance email, verified business, alert toggles | 🆕 `GET/PUT /organisations/me/profile` |

## Not on a screen yet, required by the plan

| Need | Status |
|---|---|
| Earnings settlement (hold 5 days, min views, partial thousands never billed, creator cap, pot cap, trust flags). D18 implemented from cumulative views rather than `billable_views` — see the register | 🆕 `modules/earnings` + `POST /admin/earnings/settle` + background tick |
| Audit of money and trust actions; balances derived from the domain tables (funding orders, earning entries, payouts + allocations), never a running total | 🆕 `audit_events`, `GET /admin/audit` |
| Payout reconciliation, retry and force-fail | 🔒 `payouts.reconcile` job, `POST /admin/payouts/{id}/retry`, `/fail`, provider webhook |
| Stop tracking on withdraw / close (D17, now exposed by Intelligence) | 🆕 wired |
| Admin ops (queues, payouts, funding, appeals) | 🆕 `GET /admin/…` minimal set |

## Decisions this pass made (flagged, not buried)

1. **Content verification (D11) is still unowned.** Submissions are routed
   through a `Verifier` interface. The default verifier sends every
   submission to the brand's human review queue — nothing earns until a
   human approves. A rules/AI verifier plugs in behind the same interface.
2. **Payment provider: Paystack** (D23). Everything money-moving sits behind
   `PaymentProvider`; `PAYMENT_PROVIDER=paystack` + `PAYSTACK_SECRET_KEY` turns
   it on (brands pay through a hosted checkout, `checkout_url` on the funding
   order; payouts are Paystack transfers). The default stays `sandbox`. The
   adapter is unit-tested against a scripted Paystack but has never touched
   the real API — try it in test mode first. Transfers need Paystack balance.
3. **Activation now requires confirmed funding** ("the campaign opens after
   the full amount reaches escrow"). Previously `activate` skipped it.
4. **Partial thousands** are handled on cumulative views (not per-poll
   deltas), so 900 views a poll never rounds to zero forever.

## Still open after this pass (not endpoints)

- **The frontend is still on fixtures.** Nothing in `frontend/` calls this API
  yet; it needs a client layer and real auth/session handling.
- **Paystack is untested against the real API.** Run funding and a payout in
  test mode before going live.
- **Every clip needs a human.** Brief verification (D11) has no owner; the
  review-queue UX is the interim verifier.
- **Uploaded video has no thumbnail**, so review cards show the video URL with
  no poster.
- D18 and D22 were decided by Koded without Adam's input (recorded in
  `intelligence-contracts.md`).
