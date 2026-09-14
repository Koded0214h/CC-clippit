# Clippit Backend

One monolithic FastAPI app, fully async. Every backend module (Auth &
Accounts today; Campaign Management, Content Submission, Intelligence
Engine, Payout Service, Admin as they land — see
`../architecture/backend-modules.md`) mounts its routers on the single
`app` in `main.py`. There is no per-module process, port, or venv — one
app, one server, one database.

```
backend/
  main.py                    <- entry point: uvicorn main:app
  requirements.txt
  .env.example
  alembic.ini, alembic/      <- schema migrations (source of truth for the DB)
  core/                      <- shared: config, async db session, JWT/password hashing,
                                 rate limiter, tiny TTL cache
  modules/
    auth/                    <- Auth & Accounts + Social OAuth (Koded)
      models.py               users, social_accounts, user_preferences, revoked_tokens
      schemas.py
      router.py                /auth/signup, /auth/login, /auth/logout, /auth/me
      social_router.py         /social/{platform}/login|callback, /social/accounts
      profile_router.py        /profile, /profile/preferences
      internal_router.py       /internal/* — called by other modules, not the browser
      providers/                one file per OAuth platform (tiktok, facebook, instagram, threads)
  service-test/              <- earlier standalone OAuth prototypes, kept for reference
```

## Run it

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL + provider credentials
alembic upgrade head        # creates/updates the schema — see Migrations below
uvicorn main:app --reload --port 8000
```

Needs a running Postgres reachable at `DATABASE_URL` (an `asyncpg` URL,
e.g. `postgresql+asyncpg://user:pass@host/db` — the app talks to Postgres
asynchronously end to end, including the OAuth token exchanges, which use
`httpx.AsyncClient` rather than `requests`).

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

## Social OAuth (connect-only, from the profile)

| Route | Auth | Purpose |
|---|---|---|
| `GET /social/{platform}/login?token=<jwt>` | JWT (query, see note) | starts OAuth for tiktok/facebook/instagram/threads |
| `GET /social/{platform}/callback` | — | provider redirects here; stores the connection; redirects to `{FRONTEND_ORIGIN}/profile?...` |
| `GET /social/accounts` | Bearer | list the current user's connected platforms |
| `DELETE /social/{platform}` | Bearer | disconnect a platform |

`/social/{platform}/login` takes the token as a query param instead of a
header because the frontend reaches it via a plain browser navigation from
the profile page (clicking "Connect TikTok"), which can't attach an
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

- **tiktok** — PKCE required.
- **facebook**, **instagram**, **threads** — short-lived token → long-lived
  token exchange. No refresh-token flow ported yet; a token that's expired
  by the time `/internal/social-accounts/.../token` is called returns 409
  and the creator has to reconnect.

## Performance & Trust Intelligence (Adam)

Platform reads live in `integrations/social/`, behind one interface
(`base.py`) so no platform-specific request logic exists anywhere else.
`modules/intelligence/contracts.py` holds the only types that cross out of
this domain — see `../architecture/intelligence-contracts.md` for the
boundary, the canonical data model, and the decisions register.

| Platform | Adapter | Needs creator token | Comment text |
|---|---|---|---|
| tiktok | `integrations/social/tiktok.py` | yes | no (Display API exposes counts only) |

```sh
pip install -r requirements-dev.txt
pytest                      # adapters are tested against recorded payloads, no credentials needed
```

## Known gaps (next optimization pass)

- No refresh-token flow for Facebook/Instagram/Threads (see above).
- No pruning job for expired `revoked_tokens` rows.
- Rate limiter and TTL cache are both single-process/in-memory — fine for
  one instance, need Redis before this runs as more than one.
