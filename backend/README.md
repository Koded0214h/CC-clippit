# Clippit Backend

One monolithic FastAPI app, fully async. Ownership split is Koded on core
backend (auth, campaigns, submissions, payouts, admin) and Adam on
Performance & Trust Intelligence — see `../architecture/intelligence-contracts.md`
for the frozen boundary and contracts (`architecture/backend-modules.md` is
superseded but still useful for the table sketches of modules not yet
built). Every module mounts its routers on the single `app` in `main.py`.
There is no per-module process, port, or venv — one app, one server, one
database.

```
backend/
  main.py                    <- entry point: uvicorn main:app
  requirements.txt, requirements-dev.txt
  .env.example
  alembic.ini, alembic/      <- schema migrations (source of truth for the DB)
  core/                      <- shared: config, async db session, JWT/password/OTP hashing,
                                 rate limiter, TTL cache, the canonical Platform enum,
                                 money.py (Decimal), email.py, storage.py, jobs.py, startup.py,
                                 internal_client.py (in-process client for another module's
                                 /internal/* routes over the real ASGI contract)
  integrations/
    social/                  <- platform adapters (Adam)
    payments/                <- PaymentProvider interface, Paystack adapter, deterministic sandbox (D23)
  modules/
    auth/                    <- accounts, email verify/recovery, social OAuth (Koded)
    creators/                <- profile, onboarding, bank details, clips, accounts, home
    organisations/           <- brand identity, onboarding
    campaigns/               <- brief, budget, rules, feed, stats, brand overview
    funding/                 <- funding orders (a campaign opens only when funded)
    submissions/             <- clips, verdicts (Verifier interface), appeals
    reviews/                 <- the brand's review queue
    earnings/                <- settlement rules, history, leaderboard, jobs
    payouts/                 <- withdrawals: reserve -> send -> settle; receipts
    payments/                <- bank list, signed provider webhook
    notifications/           <- inbox + notify() honouring the user's toggles
    uploads/                 <- images / videos / evidence
    audit/                   <- append-only log of money and trust actions
    admin/                   <- operator tools (every action audited)
    intelligence/            <- Performance & Trust Intelligence (Adam)
    scheduled.py             <- registers the periodic jobs
  service-test/              <- earlier standalone OAuth/platform prototypes, kept for reference
  tests/                     <- pytest: HTTP tests on real Postgres + Adam's unit suite
```

## Run it

```sh
# From the repo root: Postgres on host 5433 (avoids a Homebrew server on 5432)
docker compose up -d
cd backend
cp .env.example .env        # DATABASE_URL should use localhost:5433
alembic upgrade head
uvicorn main:app --reload --port 8000

# In a second terminal — grows time series while the API is up
cd backend && python -m modules.intelligence.worker
```

The Next.js app (`frontend/`) is on port **5174**. `FRONTEND_ORIGIN` must
include `http://localhost:5174` so the browser can call this API and so
OAuth callbacks land on `/dashboard/settings`.

Needs a running Postgres reachable at `DATABASE_URL` (an `asyncpg` URL).

## Status — what's in, what's next

Backend MVP is in. A creator can sign up, connect a platform, submit a
URL on an active campaign, and read performance + trust. Intelligence
owns adapters, snapshots, features, comments, and trust. Core already
has auth, campaigns, submissions, and creator bank-detail rows.

**Done (Adam, live-proven unless noted)**

- Adapters: TikTok, Instagram, Facebook, Threads, X, **YouTube**.
- OAuth for all six (YouTube = Google OAuth + channel identity; metrics
  use `YOUTUBE_API_KEY`). Callback lands on
  `{FRONTEND_ORIGIN}/dashboard/settings?social=…&status=ok|error`
  (first origin if the env var is a CORS list). Default origin is
  `http://localhost:5174`.
- Withdraw and campaign close call
  `POST /internal/submissions/{id}/tracking/stop`. The 30-day age cap
  is the backstop.
- `GET /campaigns/{id}/pool` — promised pot
  (`expected_views / 1000 × rate_per_1000_views`) vs what current view
  totals would cost. Returns `pot`, `allocated`, `remaining`,
  `percent_given`, `percent_remaining`. Not a transfer and not a ledger.
- Live against real accounts: TikTok, Instagram, Threads, X. Facebook
  login works; we only read **Page** posts, so a user with no Pages has
  nothing to ingest. YouTube is fixture-tested; needs a real API key +
  OAuth client to live-prove.

**Done (Koded) — see "Core product API" below**

- Auth completion (email verify, recovery), onboarding, profiles, uploads,
  notifications; campaign brief/budget/rules; funding; submissions with
  per-requirement verdicts, brand review queue and appeals; earnings
  settlement; withdrawals with receipts; admin tools; the audit log.

**Next**

- Wire the Next.js app to these endpoints (`frontend/lib/product.ts` and
  `lib/brand.ts` are still fixtures). Screen → endpoint map:
  `../architecture/api-coverage.md`.
- Align Core money/fees with PRD V1.0 (15% / 2.5% / 7% wallets) — Core lane.
- Automated brief verification (D11): enable with `COMPLIANCE_VERIFIER=qwen`
  plus `DASHSCOPE_API_KEY` (yt-dlp + Qwen3.8-Omni-Flash are implemented).
- Confirm D1, D18, D22 with Adam — Core implemented D18 and D22 in a way that
  needs his acknowledgement (see the register).
- Live-smoke YouTube with a real Data API key + OAuth client.

Contracts and the decision register:
`../architecture/intelligence-contracts.md`. Endpoint detail is in the
sections below.

## Migrations (Alembic)

The schema is defined by `modules/*/models.py` and versioned in
`alembic/versions/`. There is no `create_all` fallback — the app assumes
migrations have been run.

```sh
alembic upgrade head                          # apply pending migrations
alembic revision --autogenerate -m "message"  # after changing a model
```

When a new module adds models, import them in `alembic/env.py` (see the
comment there) so autogenerate can see them.

## Auth & Accounts endpoints

| Route | Auth | Purpose |
|---|---|---|
| `POST /auth/signup` | — | `{email, password, full_name, role}` → user + JWT. Rate limited: 3/min/IP. |
| `POST /auth/login` | — | `{email, password}` → JWT. Rate limited: 5/min/IP. |
| `POST /auth/logout` | Bearer | revokes *this* token only (see Token revocation below) |
| `GET /auth/me` | Bearer | current user (`email_verified`, `onboarding_completed`) |
| `POST /auth/verify-email` · `/auth/verify-email/resend` | Bearer or `email` | confirm the address with a 6-digit code |
| `POST /auth/forgot-password` → `/auth/recovery-code/verify` → `/auth/reset-password` | — | password recovery; single-use token, ends existing sessions |

Signup and login are the only ways to create or authenticate an account.
There is no "sign up with TikTok" — connecting a platform is a **profile**
action taken after a normal signup, handled entirely by the endpoints below.

## Profile & preferences

| Route | Auth | Purpose |
|---|---|---|
| `GET /profile` | Bearer | user + connected social accounts + preferences, in one call — what a profile page loads |
| `GET /profile/preferences` | Bearer | just the preferences |
| `PATCH /profile/preferences` | Bearer | partial update: `email_notifications`, `marketing_emails`, `theme`, and the seven `notifications` toggles |

A default preferences row is created at signup; `/profile/preferences`
lazily creates one for any account that predates this table.

## Social OAuth (connect-only, from settings)

| Route | Auth | Purpose |
|---|---|---|
| `GET /social/{platform}/login?token=<jwt>` | JWT (query, see note) | starts OAuth for tiktok/facebook/instagram/threads/x |
| `GET /social/{platform}/callback` | — | provider redirects here; stores the connection; redirects to `{FRONTEND_ORIGIN}/dashboard/settings?...` |
| `GET /social/accounts` | Bearer | list the current user's connected platforms |
| `DELETE /social/{platform}` | Bearer | disconnect a platform |

`/social/{platform}/login` takes the token as a query param instead of a
header because the frontend reaches it via a plain browser navigation from
settings (clicking "Connect TikTok"), which can't attach an
`Authorization` header. The CSRF/PKCE-carrying `state` param is what
actually secures the OAuth round trip; the query token only identifies who's
connecting.

## Internal endpoints (for other modules, not the browser)

Guarded by an `X-Internal-Secret` header (`INTERNAL_SERVICE_SECRET` in
`.env`) instead of a user JWT.

| Route | Used by | Cached |
|---|---|---|
| `GET /internal/users/{user_id}` | Campaign Management, Content Submission — resolve role/identity | 30s TTL, in-process (see `core/cache.py`) |
| `GET /internal/social-accounts/{user_id}/{platform}/token` | Intelligence Engine — read a creator's platform access token | not cached — a token is exactly what must never be served stale |

The TTL cache is deliberately minimal (one process's memory). It buys
fewer DB round trips for a lookup other modules call on nearly every
request, at the cost of up to 30s staleness if a role changes. The moment
this runs as more than one worker, or needs cross-process invalidation,
swap it for Redis — `core/cache.py` says so at the top.

## Token revocation ("logout" is real)

Every access token carries a unique `jti`. `POST /auth/logout` inserts that
`jti` into `revoked_tokens`; every authenticated request checks the
token's `jti` against that table before trusting it. This revokes **only
the token used to call logout** — other sessions/devices for the same user
stay valid. Rows can be pruned once `expires_at` has passed (no scheduled
job for that yet — a TODO once this needs to run for real).

## Rate limiting

`slowapi`, configured in `core/rate_limit.py`, in-memory by default
(`RATE_LIMIT_STORAGE_URI=memory://`). `/auth/login` (5/min) and
`/auth/signup` (3/min) are limited per client IP. **In-memory means limits
are per-process** — the moment this runs as more than one uvicorn worker or
more than one instance, point `RATE_LIMIT_STORAGE_URI` at Redis
(`redis://host:6379`) or the limit becomes N× too generous.

## Roles

`creator`, `organisation` (the "event manager" actor in the architecture
doc — named to match the frontend's existing `AccountRole` type), `admin`.
Admin accounts aren't self-service — `POST /auth/signup` rejects `role: admin`.

## Social OAuth providers

`modules/auth/providers/` ports the OAuth handshake from the standalone
prototypes in `service-test/{tt,meta_fb,meta_insta,meta_threads,x}` — same
endpoints, same token-exchange steps, normalized into one `NormalizedToken`
shape, now on `httpx.AsyncClient` instead of `requests`. Only the
*connect-an-account* step is ported here; each platform's metrics/content
endpoints (video list, Page posts, Threads insights, etc.) belong to the
Intelligence Engine module, not Auth.

- **tiktok**, **x** — PKCE required.
- **facebook**, **instagram**, **threads** — short-lived token → long-lived
  token exchange. No refresh-token flow ported yet; a token that's expired
  by the time `/internal/social-accounts/.../token` is called returns 409
  and the creator has to reconnect.

## Core product API

Everything the frontend screens call, by area. The mapping from each screen
to its endpoints — and what was missing before — is in
`../architecture/api-coverage.md`. All money is `Decimal` in code and
`NUMERIC(14,2)` in Postgres; JSON carries plain numbers.

### Campaigns (brand)

A campaign is built as a `draft` (brief, rules, budget), **funded**, and only
then goes `active`. Its terms are locked from the moment funding starts.

| Route | Who | Purpose |
|---|---|---|
| `POST /campaigns` | organisation (verified email) | create a draft: title, tagline, description, category, source link, platforms, `pot` *or* `expected_views`, duration, payout rule, rules[], cover |
| `GET /campaigns` | any | brand: own, any status. Others: live. Filters `q`, `category`, `platform`, `feed=for_you\|joined\|closing_soon\|open`, `status_filter`, paging |
| `GET /campaigns/{id-or-slug}` | any | one campaign; drafts 404 for outsiders |
| `PATCH /campaigns/{id}` · `PUT …/payout-rule` · `GET/PUT …/rules` | owner/admin, **draft only** | edit; rules are replaced as a whole list |
| `POST …/pause` · `…/resume` | owner/admin | stop/allow *new* entries; existing clips keep earning |
| `POST …/close` | owner/admin | books the views earned so far, then closes; stops tracking |
| `GET …/stats` · `…/submissions` · `…/report` | owner/admin | the live-campaign screen: pot drawn down, verified views, the last-24h delta, the review pipeline; recent submissions; CSV (formula-injection safe) |
| `GET /brand/overview` | organisation | pending reviews, live/draft/completed counts, spend, 24h views & earnings, the featured live campaign |
| `GET /brand/recommendations/trends` | organisation | current campaign ideas from recent approved posts in the brand's onboarding interests; includes evidence size, freshness, and an empty-state message when the sample is too small |

**The budget identity.** Send `pot` (what the brand budgets) or
`expected_views` (what that buys); the other is derived at the payout rate.
`₦500,000 ÷ ₦500 × 1,000 = 1,000,000` views — floored, because partial
thousands are never billed. Changing the rate rescales the views; the pot
is the promise.

**Creator cards** (`feed_status`: Open / Closing soon / Joined, `time_left`,
`spent`/`remaining`, brand name & verified flag) carry no `metrics`; the
owning brand's cards do.

### Funding — a campaign cannot open without money

| Route | Purpose |
|---|---|
| `POST /campaigns/{id}/funding {method}` | creates the order (or returns the open one — safe to repeat). Quote = pot + 1.5% fee; bank method returns the collection account. Locks the terms |
| `GET …/funding` | the latest order |
| `POST …/funding/confirm` | "I have funded the pot": asks the provider whether it arrived. Only a provider-confirmed payment opens the campaign — the brand's word never does |
| `DELETE …/funding` | cancel an unpaid order → back to `draft` (refused once payment is claimed) |
| `POST /webhooks/payments` | provider webhook. Signature verified **before** the body is read; idempotent; short payments don't open; unknown references are acknowledged, not errored |
| `POST /campaigns/{id}/activate` | opens a campaign whose order is confirmed; 409 otherwise |

Card numbers never touch this API — they go to the provider's hosted fields.

### The payment provider boundary

`integrations/payments.PaymentProvider` is the only door to a bank or
provider: collections, bank list, account resolution, transfers, webhook
verification. Decision D23 (Squad vs Paystack vs Payaza) is open, so the
default is a **deterministic sandbox** that never touches a network:
accounts ending `0000` don't exist / are rejected, `9999` settle
asynchronously by webhook, everything else succeeds. Responses carry
`sandbox: true`. `core/startup.py` refuses to boot with
`ENVIRONMENT=production` and the sandbox, default secrets, or the console
mailer. Writing a real provider = one adapter + one line in
`integrations/payments/__init__.py`.

### Submissions, verification and reviews

`POST /submissions` (verified creator): the campaign must be live, not
paused, not past its deadline, accept the platform, and the creator must
have that platform connected; an optional `video_upload_id` must be the
creator's own video. Intelligence registers the link (ownership); a link it
rejects is **kept** as `rejected` with its reason. Then a `Verifier` checks
the clip against the brief.

Decision D11 (who builds real verification) is unassigned, so the default
`ManualReviewVerifier` sends every clip to the brand's review queue —
**nothing earns until a person approves** — and a campaign with no
requirements approves outright. An automated verifier is one class behind
`submissions.verification.Verifier`.

| Route | Who | Purpose |
|---|---|---|
| `GET /submissions/{id}` | creator/brand/admin | the verdict: per-requirement pass/fail/review with notes, the failed requirement, the four progress `steps`, any appeal |
| `POST /submissions/{id}/appeal {reason ≥20, evidence_upload_id?}` | creator | "Request review". One appeal per verdict; the original is never edited |
| `GET /submissions/{id}/earnings` | visible | accrued so far, payable now, when the next amount clears |
| `GET /creators/me/clips` | creator | My clips: rows + totals (Approved / Checking / Needs attention / …) |
| `GET /brand/reviews?tab=needs_review\|appeals\|resolved` | brand/admin | the queue with tab counts, oldest first |
| `GET /brand/reviews/{id}` · `POST …/approve` · `POST …/request-correction {reason, requirement_id?}` | brand/admin | decide. Approving books what the clip already earned; on an appeal, approving overturns the rejection |

### Earnings

`modules/earnings/service.py` is the whole set of rules, and every one has a
test: only an **approved** clip on a **live** campaign earns; nothing below
the minimum views; billing is per whole thousand of **cumulative** views
(so partial thousands roll forward and a downward revision never claws money
back); a per-creator cap across all their clips; **the pot is a hard ceiling**
enforced under a row lock (two clips cannot both spend the last of it, and an
empty pot closes the campaign); a `flagged` clip accrues nothing until the flag
clears (D22); every accrual is held 5 days (`EARNINGS_HOLD_DAYS`) and carries the
Intelligence snapshot it came from. Entries have a unique
`<submission>:<thousands billed>` reference, so retries and concurrent runs
cannot pay a thousand twice.

| Route | Purpose |
|---|---|
| `GET /earnings/summary` | payable · in hold · processing · paid all time · lifetime views · next clear date |
| `GET /earnings/history` | each accrual: clip, campaign, billable views, amount, state (Accrued/Payable/Processing/Paid) |
| `GET /leaderboard?period=week\|all&campaign_id=` | creators by verified views, plus the caller's own rank |

### Payouts

Reserve → send → settle (`modules/payouts/service.py` explains why the
order matters): the money is reserved under a lock and committed *before*
the provider is called, with the payout's `reference` as the provider-side
idempotency key. A crash between the two leaves a `pending` payout that the
reconciliation job sends — and the provider de-duplicates on the reference.
A failure returns the money to `payable` by ceasing to count its allocation;
nothing is ever edited back.

| Route | Purpose |
|---|---|
| `GET /banks` · `POST /banks/resolve` | bank list; look an account up before saving it |
| `PUT/GET /creators/me/bank-details` · `POST …/verify` | save (resets verification), read (masked), verify with the provider |
| `POST /payouts {amount, idempotency_key}` | withdraw (≥ ₦1,000, ≤ payable, verified account). A repeated key returns the same payout |
| `GET /payouts` · `GET /payouts/{id}` | history; the receipt with `provenance` ("where this money came from") |

### Admin

Admin-only, and every action that changes money or trust state writes an
audit event naming the admin.

`GET /admin/overview` · `GET /admin/payouts` · `POST /admin/payouts/{id}/retry|fail` ·
`GET /admin/funding` · `POST /admin/funding/{id}/confirm` (needs the full amount + a note) ·
`GET /admin/earnings/blocked` · `POST /admin/earnings/settle` · `POST /admin/campaigns/sweep` ·
`POST /admin/organisations/{id}/verify-business` (the only way `business_verified` is set) ·
`GET /admin/audit`.

### Onboarding, profiles, uploads, notifications

| Route | Purpose |
|---|---|
| `PUT /creators/me/onboarding` · `GET/PUT /creators/me/profile` | name, content lanes, platforms, discovery/experience/goals, photo |
| `PUT /organisations/me/onboarding` · `GET/PUT /organisations/me/profile` | org identity, funding contact, content/viewing interests used by brand trend recommendations; `business_verified` is read-only here |
| `GET /creators/me/accounts` | every platform, connected or not, with handle and when its views were last read |
| `GET /creators/me/overview` | dashboard home: closest-to-closing campaign, new lane matches, earnings |
| `POST /uploads/images\|videos\|evidence` | streamed, size-capped, type sniffed from bytes; media served at `/media/…` |
| `GET /notifications` · `POST …/{id}/read` · `POST …/read-all` | the inbox. `notify()` honours the toggles in `PATCH /profile/preferences`; money outcomes ignore them |

### Auth additions

`POST /auth/verify-email`, `/auth/verify-email/resend`, `/auth/forgot-password`,
`/auth/recovery-code/verify`, `/auth/reset-password`. Codes are six digits
stored as HMACs, expire, allow 5 guesses and can't be re-requested inside the
cooldown; `forgot-password` never reveals whether an account exists; a reset
token is single-use and a reset ends every existing session. Spending and
publishing endpoints require a verified email. Email goes through
`core/email.py` — printed to the console by default (that print *is* the dev
inbox), SMTP with `EMAIL_BACKEND=smtp`.

### Background jobs

`BACKGROUND_JOBS_ENABLED=true` starts, inside the API process:
`earnings.settle` (5 min), `campaigns.sweep` (5 min — books final views, then
closes on the deadline), `earnings.notify_payable` (15 min), `payouts.reconcile`
(2 min), `intelligence.poll` (tick from `INTELLIGENCE_POLL_TICK_SECONDS`).
All are idempotent and safe to skip; each settles one clip per
transaction so a bad clip stops nothing. It is the same shape as
Intelligence's worker: replace the runner (decision D4) and the functions stay.

### Testing

```sh
pytest                      # ~390 tests; needs Postgres on localhost:5433
```

HTTP tests run the real app against a real Postgres schema. Intelligence is
faked at the one seam core uses (`tests/fakes.py`): scriptable views, trust
flags and outages. `tests/test_end_to_end.py` walks the whole product —
fund, submit, approve, earn, hold, withdraw, audit.


## Performance & Trust Intelligence (Adam)

Platform reads live in `integrations/social/`, behind one interface
(`base.py`) so no platform-specific request logic exists anywhere else.
`modules/intelligence/contracts.py` holds the only types that cross out of
this domain — see `../architecture/intelligence-contracts.md` for the
boundary, the canonical data model, and the decisions register.

| Platform | Adapter | Needs creator token | Comment text |
|---|---|---|---|
| tiktok | `integrations/social/tiktok.py` | yes | no (Display API exposes counts only) |
| instagram | `integrations/social/instagram.py` | yes | yes |
| facebook | `integrations/social/facebook.py` | yes | yes |
| threads | `integrations/social/threads.py` | yes | yes |
| x | `integrations/social/x.py` | no (twitterapi.io key) | yes |
| youtube | `integrations/social/youtube.py` | no (Data API key) | yes |

PRD V1 platforms are `core.platforms.V1_PLATFORMS` (Instagram, TikTok,
Facebook, X, YouTube). Threads remains implemented but is outside V1.

Ingestion (`modules/intelligence/ingestion.py`) turns a submission into
stored observations:

```
IngestionService.ingest(SubmissionRef)
    social_content    one row per submission — identity, resolved once and reused
    metric_snapshots  one row per reading — append-only, never updated
```

Identity is resolved on the first ingest only, so polling a submission
costs one API call per poll rather than three. The service doesn't commit
(the caller owns the transaction) and doesn't retry — adapter errors
propagate for the Stage 3 poller to interpret.

Creator tokens are read through auth's
`/internal/social-accounts/{user_id}/{platform}/token` behind the
`TokenSource` port in `tokens.py`. This module never imports auth's models
or queries `social_accounts`.

Polling keeps that series growing. `scheduling.py` holds the policy as
pure functions (how often to poll by post age; what a given failure
means); `polling.py` applies it:

```
PollingCoordinator.start(SubmissionRef)   first reading, then queue it
                  .run_due()              one tick — claim, poll, reschedule
                  .stop() / .resume()     campaign ended / creator reconnected
```

| Post age | Polled every |
|---|---|
| < 24h | 30 min |
| < 7 days | 2 hours |
| < 30 days | 12 hours |
| ≥ 30 days | tracking stops |

A tick claims due work by pushing `next_poll_at` forward before any
network call (`FOR UPDATE SKIP LOCKED` on Postgres), so several workers
can run at once and a worker that dies mid-poll doesn't strand its rows.
Each submission gets its own transaction and a poll never raises — every
failure is recorded as a decision: retry with backoff, stop and tell the
creator, or dead-letter for a human.

```sh
python -m modules.intelligence.worker     # asyncio loop, 60s tick
```

That loop is a placeholder for decision D4 (Inngest vs Celery vs
APScheduler). Nothing else in the module knows about a runtime — a hosted
scheduler's handler body is `await coordinator.run_due()`.

### Internal routes

| Route | Purpose | Talks to a platform? |
|---|---|---|
| `POST /internal/submissions/{id}/metrics` | Register a submission (`SubmissionRef` body → 201) or force a fresh reading | yes |
| `GET /internal/submissions/{id}/performance` | Everything we know, from our tables | never |
| `GET /internal/submissions/{id}/trust` | Latest trust verdict | never |
| `GET /internal/submissions/{id}/intelligence` | Performance + trust in one response | never |
| `POST /internal/submissions/{id}/trust/review` | Record a human label | never |
| `GET /internal/trust/rules` | Thresholds currently in force | never |
| `POST /internal/submissions/{id}/tracking/stop` | Campaign closed or creator withdrew | never |
| `POST /internal/submissions/{id}/tracking/resume` | Put a stopped submission back on the queue | never |

Billing uses the GET, so a payout run is never slow or wrong because
TikTok is down. Pass `?since_snapshot_id=` — the `provenance.snapshot_id`
you last settled against — to get `features.billable_views`, which is the
only view figure that gives the same answer twice and is therefore safe
to retry. `features.incremental_views` is relative to the previous poll
and is a velocity input, not a billing number.

Derived values (`content_features`) are stored per snapshot and are
disposable: `FeatureService.recompute_all()` rebuilds them from the
observations, so improving the velocity formula corrects history instead
of requiring a refetch.

```sh
pip install -r requirements-dev.txt
pytest                      # adapters + intelligence: fixtures / in-memory SQLite
```

Adapter tests use recorded JSON, no live logins. Intelligence uses
in-memory SQLite. Auth / campaigns / submissions HTTP tests need Docker
Postgres on **5433** (`tests/http_app.py`) and skip if it isn't up.

## Known gaps (next optimization pass)

- No refresh-token flow for Facebook/Instagram/Threads (see above).
- No pruning job for expired `revoked_tokens` rows.
- Rate limiter and TTL cache are both single-process/in-memory — fine for
  one instance, need Redis before this runs as more than one.
- Money paths are complete but have never moved real money: the provider is a
  sandbox (D23). Reconciliation against a real provider's statements is
  unwritten.
- Media is served from local disk under unguessable URLs; R2 with signed URLs
  is the production plan.
- Nothing extracts a thumbnail from an uploaded video, so review cards have
  the video URL but no poster image.
- Rate limits and the TTL cache are per-process; the periodic jobs run in the
  API process. Both need to move (Redis / a real scheduler) before running more
  than one instance — and `payouts.reconcile`/`earnings.settle` must then run in
  exactly one place (they are idempotent, so a duplicate is safe, but wasteful).
