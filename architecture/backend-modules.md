# Clippit Backend — Module Breakdown

Based on `architecture/clippit-architecture.excalidraw`. Each module lists its
scope, what it owns (DB tables / external APIs), and what it depends on from
other modules — so a split can be made along a clean boundary rather than a
shared table or shared code path.

---

## 1. Auth & Accounts
User signup/login for all three actors (event manager, creator, admin), sessions/JWT, roles & permissions.

- **Owns:** `users`, `roles`, sessions/token issuance
- **Depends on:** nothing
- **Exposes to others:** current-user identity + role, used by every other module

## 2. Campaign Management
Event manager creates and manages campaigns: title, description, expected views, platforms, payout rules, status (draft/active/closed).

- **Owns:** `campaigns`, `payout_rules` tables
- **Depends on:** Auth (event manager identity)
- **Exposes to others:** campaign data + payout rules, read by Content Submission, Intelligence Engine, Admin

## 3. Campaign Funding (Paystack — money in)
Creates the Paystack virtual account per campaign, confirms funding, tracks campaign balance.

- **Owns:** `campaign_accounts`/`ledger` table, Paystack "create virtual account" + webhook handling
- **Depends on:** Campaign Management (a campaign must exist)
- **Exposes to others:** available balance, checked by Payout Service before a transfer

## 4. Social Account Connections (OAuth) — merged into Auth & Accounts
Creator connects TikTok (and later IG/others) via OAuth, stores/refreshes tokens. This is the service already built in `service-test/tt`. Folded into module 1 rather than kept separate — same owner, same `users` identity, no reason to split it across a network boundary.

- **Owns:** `social_accounts` table (tokens, refresh tokens, platform user id)
- **Depends on:** Auth (creator identity)
- **Exposes to others:** a valid access token per creator+platform, used by Intelligence Engine

## 5. Content Submission
Creator picks a campaign, uploads/describes content, submits the video URL for verification.

- **Owns:** `submissions` table (creator, campaign, video URL, status)
- **Depends on:** Campaign Management (must pick a real, active campaign), Auth
- **Exposes to others:** a submission record for the Intelligence Engine to process

## 6. Intelligence Engine (verify + calculate)
Fetches views/likes for a submitted video (via the platform's API, using the token from module 4), checks it's legitimate for the campaign, calculates the payout from the campaign's payout rules. **Never touches money.**

- **Owns:** `verified_results` table (views, likes, computed payout amount, status)
- **Depends on:** Social Account Connections (token), Content Submission (video URL), Campaign Management (payout rules)
- **Exposes to others:** a verified result, consumed only by Payout Service

## 7. Payout Service (move money)
Takes a verified result, collects/validates the creator's bank details, verifies the account with Paystack, initiates the transfer, handles retries/failures. **The only module allowed to move money.**

- **Owns:** `bank_accounts`, `payouts`/`transfers` tables, Paystack "resolve account" + "transfer" + webhook handling
- **Depends on:** Intelligence Engine (verified result), Campaign Funding (balance to draw from)
- **Exposes to others:** payout status, read by Admin

## 8. Admin & Oversight
Read-only monitoring of campaigns and payouts, flag review, dispute resolution, manual overrides on stuck/disputed payouts.

- **Owns:** `disputes`/`flags` table, override actions on Payout Service
- **Depends on:** Campaign Management, Intelligence Engine, Payout Service (reads across all three)
- **Exposes to others:** nothing — this is a consumer, not a dependency, of everything else

---

## Assignment

| Module | Owner |
|---|---|
| 1. Auth & Accounts *(includes Social Account Connections)* | **Koded** |
| 2. Campaign Management | **Adam** |
| 3. Campaign Funding | **Adam** |
| 4. Content Submission | **Adam** |
| 5. Intelligence Engine | **Koded** |
| 6. Payout Service | **Koded** |
| 7. Admin & Oversight | **Adam** |

Koded ends up owning **identity + verification + money-out**: who someone is,
whether a video is legitimate, and moving the payout. Adam owns **campaigns +
money-in + oversight**: what a campaign promises, funding it, collecting
submissions against it, and watching the whole thing run. Each side is a
separate service (or at least a separate module boundary) talking to the
other only through the internal endpoints below — nobody reaches into the
other's tables directly.

---

## Koded — Auth, Intelligence Engine, Payout Service

### 1. Auth & Accounts
- **Tables:** `users(id, email, password_hash, role, created_at)`, `social_accounts(id, user_id, platform, platform_user_id, access_token, refresh_token, expires_at)`
- **Public endpoints:** `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `GET /auth/social/:platform/login`, `GET /auth/social/:platform/callback`
- **For internal use:** JWT verification (shared middleware/JWKS) that Adam's services validate against; `GET /internal/users/:id` for role/profile lookups

### 5. Intelligence Engine
- **Tables:** `verified_results(id, submission_id, campaign_id, creator_id, platform, views, likes, payout_amount, status, verified_at)`
- **Trigger:** Adam's Content Submission calls `POST /engine/verify {submission_id}` right after a submission is created (or queues it — pick one, see open questions)
- **Reads from Adam:** `GET /internal/submissions/:id` (video URL, creator_id, campaign_id), `GET /internal/campaigns/:id` (payout rules, status, platform)
- **Reads from own Auth module:** the creator's platform access token
- **Writes:** a `verified_results` row; on success, calls Payout Service's `POST /payouts/initiate` internally (same owner, in-process or queued)
- **Never:** touches `bank_accounts`, `payouts`, or any Paystack transfer/balance call

### 6. Payout Service
- **Tables:** `bank_accounts(id, creator_id, bank_code, account_number, account_name, verified)`, `payouts(id, verified_result_id, campaign_id, amount, status, paystack_transfer_id, created_at, updated_at)`
- **Public endpoints:** `POST /payouts/bank-details` (creator submits bank info), `GET /payouts/:id`
- **Internal endpoints (called by Adam's Admin module):** `GET /internal/payouts?campaign_id=`, `POST /internal/payouts/:id/override` (admin-triggered retry/force-fail, still executed here — Admin never talks to Paystack directly)
- **Reads from Adam:** `GET /internal/campaigns/:id/balance`, `POST /internal/campaigns/:id/debit` (Campaign Funding owns the ledger; Payout Service must debit through it, not by writing to Adam's table)
- **Talks to:** Paystack (resolve account, initiate transfer, transfer webhook)

---

## Adam — Campaign Management, Campaign Funding, Content Submission, Admin

### 2. Campaign Management
- **Tables:** `campaigns(id, event_manager_id, title, description, expected_views, platforms, status, created_at)`, `payout_rules(id, campaign_id, rate_per_1000_views, cap_amount, min_views_threshold)`
- **Public endpoints:** `POST /campaigns`, `GET /campaigns`, `GET /campaigns/:id`, `PATCH /campaigns/:id`, `POST /campaigns/:id/payout-rules`
- **Depends on:** Koded's Auth (event manager identity via JWT middleware)
- **Serves to Koded:** `GET /internal/campaigns/:id` — status, platforms, and payout rules, read by Intelligence Engine

### 3. Campaign Funding
- **Tables:** `campaign_accounts(id, campaign_id, paystack_virtual_account_id, funded_amount, balance)`
- **Public endpoints:** `POST /campaigns/:id/fund`, `POST /webhooks/paystack/funding`
- **Depends on:** Campaign Management (campaign must exist), Paystack (create virtual account)
- **Serves to Koded:** `GET /internal/campaigns/:id/balance`, `POST /internal/campaigns/:id/debit` — the *only* way Payout Service reduces a campaign's funds

### 4. Content Submission
- **Tables:** `submissions(id, creator_id, campaign_id, video_url, status, submitted_at)`
- **Public endpoints:** `POST /submissions`, `GET /submissions/:id`, `GET /creators/:id/submissions`
- **Depends on:** Campaign Management (must be an active campaign), Koded's Auth (creator identity)
- **Serves to Koded:** `GET /internal/submissions/:id`, and triggers verification by calling Koded's `POST /engine/verify` after insert

### 7. Admin & Oversight
- **Tables:** `disputes(id, related_type, related_id, raised_by, status, resolution_notes)`
- **Public endpoints:** `GET /admin/campaigns`, `GET /admin/submissions`, `GET /admin/payouts`, `POST /admin/disputes`, `POST /admin/payouts/:id/override`
- **Reads from Koded:** `GET /internal/payouts` (list/filter), and calls `POST /internal/payouts/:id/override` — Admin never calls Paystack itself, it always goes through Payout Service
- **Reads from own modules:** campaigns, submissions
- **Produces nothing anyone else depends on** — this is the one module that's a pure consumer

---

## Open questions to settle before either of you starts

1. **Sync vs. async handoff into the engine.** A direct HTTP call from Content Submission to `/engine/verify` is simplest to build first; a queue (e.g. a Postgres outbox or a lightweight job queue) is more resilient once verification can be slow or retried. Pick sync for v1, note the queue as a follow-up.
2. **Where does `/internal/*` actually live?** Same host with a shared network/auth secret, or genuinely separate services behind an API gateway. Decide this before either of you writes the client for the other's internal endpoints.
3. **Idempotency on `POST /internal/campaigns/:id/debit`.** A retried payout must not double-debit a campaign — needs an idempotency key (e.g. the `payout.id`) from day one.
4. **Shared migration/schema tooling.** Whether both of you run one Postgres with separate schemas (`auth.*`, `campaigns.*`) or genuinely separate databases changes how `/internal` calls are implemented (a DB read vs. a real HTTP call).
