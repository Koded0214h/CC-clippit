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
  core/                      <- shared: config, async db session, JWT/password hashing,
                                 rate limiter, tiny TTL cache, the canonical Platform enum,
                                 internal_client.py (in-process client for calling another
                                 module's /internal/* routes over the real ASGI contract)
  integrations/social/       <- platform adapters (Adam) — see Performance & Trust Intelligence below
  modules/
    auth/                    <- Auth & Accounts + Social OAuth (Koded)
      models.py               users, social_accounts, user_preferences, revoked_tokens
      schemas.py
      router.py                /auth/signup, /auth/login, /auth/logout, /auth/me
      social_router.py         /social/{platform}/login|callback, /social/accounts
      profile_router.py        /profile, /profile/preferences
      internal_router.py       /internal/* — called by other modules, not the browser
      providers/                one file per OAuth platform (tiktok, facebook, instagram, threads, x)
    campaigns/                <- Campaign Management (Koded) — see below
    submissions/               <- Content Submission (Koded) — see below
    creators/                   <- Creators / bank details (Koded) — see below
    intelligence/                <- Performance & Trust Intelligence (Adam) — see below
  service-test/               <- earlier standalone OAuth/platform prototypes, kept for reference
  tests/                       <- pytest suite (SQLite in-memory; see conftest.py)
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
| `GET /auth/me` | Bearer | current user |

Signup and login are the only ways to create or authenticate an account.
There is no "sign up with TikTok" — connecting a platform is a **profile**
action taken after a normal signup, handled entirely by the endpoints below.

## Profile & preferences

| Route | Auth | Purpose |
|---|---|---|
| `GET /profile` | Bearer | user + connected social accounts + preferences, in one call — what a profile page loads |
| `GET /profile/preferences` | Bearer | just the preferences |
| `PATCH /profile/preferences` | Bearer | partial update: `email_notifications`, `marketing_emails`, `theme` |

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

## Campaign Management (Koded)

An event manager (`role: organisation`) creates a campaign as a `draft`,
sets its payout rule, then `activate`s it — only then can a creator see or
submit against it. Once active, the campaign's terms are locked (title,
description, expected views, platforms, payout rule) so a creator is never
chasing a moving target; only an admin can still correct it. `close` ends
a campaign from any state, including cancelling a draft outright.

| Route | Auth | Purpose |
|---|---|---|
| `POST /campaigns` | organisation | create a `draft` campaign + its payout rule in one call |
| `GET /campaigns` | Bearer | organisation: own campaigns, any status. Everyone else: `active` only (browsing) |
| `GET /campaigns/{id}` | Bearer | a draft 404s for anyone but its owner/admin — existence isn't leaked |
| `PATCH /campaigns/{id}` | owner or admin | edits allowed only while `draft` (admin bypasses the lock) |
| `PUT /campaigns/{id}/payout-rule` | owner or admin | replace the rule; same draft-only lock |
| `POST /campaigns/{id}/activate` | owner or admin | `draft` → `active`; 409 without a payout rule set |
| `POST /campaigns/{id}/close` | owner or admin | `draft` or `active` → `closed` (terminal) |

`platforms` validates against `core.platforms.Platform` (the same
canonical list Intelligence uses) but is stored as a plain string array,
not a native Postgres enum — deliberately, to avoid a third enum type
constraining the same values as auth's `platform` type and Intelligence's
checked varchars (see decision D5 in `intelligence-contracts.md`).
`event_manager_id` on `campaigns` *is* a real foreign key to `users.id`,
unlike Intelligence's tables — Campaign Management and Auth share one
owner, so there's no cross-team-migration reason to avoid it here.

No automated tests yet (verified so far by a manual Postgres smoke test
covering every role/state transition above) — bringing this module's
coverage up to the intelligence suite's standard is the next thing to do
here, not a gap to carry forward silently.

## Content Submission (Koded)

A creator submits a link against an `active` campaign. This module owns
only the submission's *own* lifecycle — performance and trust are never
copied onto it; every read goes live to Intelligence's internal API via
`core/internal_client.py` (`httpx.ASGITransport` against this same app —
no socket, but the real routes, the real `X-Internal-Secret` dependency,
the real `PerformanceResult`/error contract).

| Route | Auth | Purpose |
|---|---|---|
| `POST /submissions` | creator | validates campaign is active + accepts the platform + creator has that platform connected, then registers with Intelligence |
| `GET /submissions` | Bearer | creator: own. organisation: submissions against its campaigns. admin: all. `?campaign_id=` filters any of them |
| `GET /submissions/{id}` | Bearer | same visibility rule, 404s (not 403) when it's not yours to see |
| `POST /submissions/{id}/withdraw` | creator (own) or admin | terminal; org cannot withdraw a creator's submission |
| `GET /submissions/{id}/performance` | Bearer | visibility-checked proxy onto Intelligence's `GET .../performance`; pass `?since_snapshot_id=` for `billable_views` (decision D18) |

**Registration failure is not silently dropped.** If Intelligence rejects
the URL (unreadable, content unavailable, creator's token expired, rate
limited, ...), the submission row is still kept — `status: rejected` with
`rejection_code`/`rejection_message` from Intelligence's own error body —
and the same error is returned to the creator. There's an audit trail for
"why wasn't this accepted" instead of a submission just not existing.

**A real integration gap this surfaced, not caused:** Intelligence's own
`InternalApiTokenSource` (`modules/intelligence/tokens.py`) calls Auth's
token endpoint over a real HTTP loopback to a **hardcoded**
`http://127.0.0.1:8000` (decision D14 — deliberately a real network call,
not an in-process one, unlike this module's `internal_client.py`). Run
the app on any other port and that lookup fails with `upstream_error`
until someone notices the 502. Confirmed the failure path itself is
correct — a submission made this way is honestly marked `rejected` with
the real reason, never silently wrong — but the hardcoded port should
become a setting. Flagging for Adam rather than editing his module here.

No automated tests yet, same as Campaign Management — smoke-tested
end-to-end against real Postgres, including cross-creator/cross-org
visibility isolation and the rejection-audit path above.

## Creators (Koded)

Scoped to bank details only — the one piece Payment Orchestration is
actually blocked on. Profile fields (bio, interests, used for campaign
notification matching per the plan's §19.2) are real work but not on the
critical path to a payout, so they're deferred rather than built
speculatively alongside this.

| Route | Auth | Purpose |
|---|---|---|
| `PUT /creators/me/bank-details` | creator | set or replace; always resets `verified` to `false` |
| `GET /creators/me/bank-details` | creator | own details, `account_number` masked to last 4 digits |
| `GET /creators/{creator_id}/bank-details` | admin only | dispute/support access — an organisation has no reason to see this, so it doesn't follow campaigns'/submissions' owner-or-admin pattern |

One bank account per creator (`creator_id` is the primary key). This
module only **stores** what a creator enters — it does not call a payment
provider to resolve or verify an account name. `verified`/`verified_at`/
`account_name` exist on the table and stay `null`/`false` until Payment
Orchestration (next) sets them after actually checking with the provider;
Payments owns the provider abstraction, this module owns the data.
Replacing bank details always resets `verified`, so a changed payout
destination can never coast on an old verification.

No automated tests yet, same as the other core-backend modules —
smoke-tested against real Postgres: role enforcement, masking, the
verification-resets-on-change guarantee, and access isolation (a creator
can't see another creator's details, an organisation can't see any
creator's details, only admin can via the support route).

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
