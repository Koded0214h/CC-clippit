# API coverage — what the screens need vs what the backend serves

Snapshot of 2026-09-21. Method: every route under `frontend/app/` and the
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
| Home | featured/closing campaign, earnings summary | ⚠️ campaign fields extended; 🆕 `GET /earnings/summary` |
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
| Earnings settlement (D18: bill from Intelligence, hold 5 days, min views, partial thousands never billed, creator cap, pot cap) | 🆕 `modules/earnings` + `POST /admin/earnings/settle` + background tick |
| Ledger for funding, accrual and payout | 🆕 `ledger_entries` |
| Payout reconciliation + retry / override | 🔒 `POST /admin/payouts/{id}/retry`, `/override`, provider webhook |
| Stop tracking on withdraw / close (D17, now exposed by Intelligence) | 🆕 wired |
| Admin ops (queues, payouts, funding, appeals) | 🆕 `GET /admin/…` minimal set |

## Decisions this pass made (flagged, not buried)

1. **Content verification (D11) is still unowned.** Submissions are routed
   through a `Verifier` interface. The default verifier sends every
   submission to the brand's human review queue — nothing earns until a
   human approves. A rules/AI verifier plugs in behind the same interface.
2. **Payment provider is undecided** (plan §26: Squad vs Paystack; the
   frontend copy says Payaza). Everything money-moving sits behind
   `PaymentProvider`. The default is `sandbox`: deterministic, no network,
   and it says so in every response. No real transfer can happen until a real
   provider adapter is written and `PAYMENT_PROVIDER` is set.
3. **Activation now requires confirmed funding** ("the campaign opens after
   the full amount reaches escrow"). Previously `activate` skipped it.
4. **Partial thousands** are handled on cumulative views (not per-poll
   deltas), so 900 views a poll never rounds to zero forever.
