# Clippit Backend

One monolithic FastAPI app. Every backend module (Auth & Accounts today;
Campaign Management, Content Submission, Intelligence Engine, Payout
Service, Admin as they land — see `../architecture/backend-modules.md`)
mounts its routers on the single `app` in `main.py`. There is no per-module
process, port, or venv — one app, one server, one database.

```
backend/
  main.py                    <- entry point: uvicorn main:app
  requirements.txt
  .env.example
  core/                      <- shared: config, db session, JWT/password hashing
  modules/
    auth/                    <- Auth & Accounts + Social OAuth (Koded)
      models.py               users, social_accounts tables
      schemas.py
      router.py                /auth/signup, /auth/login, /auth/me
      social_router.py         /social/{platform}/login|callback, /social/accounts
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
uvicorn main:app --reload --port 8000
```

Needs a running Postgres reachable at `DATABASE_URL`. Tables are created
automatically on startup for now (`core/database.py:init_db`); switch to
Alembic migrations once the schema needs to change without dropping data.

## Auth & Accounts endpoints

| Route | Auth | Purpose |
|---|---|---|
| `POST /auth/signup` | — | `{email, password, full_name, role}` → user + JWT |
| `POST /auth/login` | — | `{email, password}` → JWT |
| `GET /auth/me` | Bearer | current user |
| `GET /social/{platform}/login?token=<jwt>` | JWT (query, see note) | starts OAuth for tiktok/facebook/instagram/threads |
| `GET /social/{platform}/callback` | — | provider redirects here; stores the connection |
| `GET /social/accounts` | Bearer | list the current user's connected platforms |
| `DELETE /social/{platform}` | Bearer | disconnect a platform |

`/social/{platform}/login` takes the token as a query param instead of a
header because the frontend reaches it via a plain browser navigation
(clicking "Connect TikTok"), which can't attach an `Authorization` header.
The CSRF/PKCE-carrying `state` param is what actually secures the OAuth
round trip; the query token only identifies who's connecting.

## Internal endpoints (for other modules, not the browser)

Guarded by an `X-Internal-Secret` header (`INTERNAL_SERVICE_SECRET` in
`.env`) instead of a user JWT.

| Route | Used by |
|---|---|
| `GET /internal/users/{user_id}` | Campaign Management, Content Submission — resolve role/identity |
| `GET /internal/social-accounts/{user_id}/{platform}/token` | Intelligence Engine — read a creator's platform access token |

## Roles

`creator`, `organisation` (the "event manager" actor in the architecture
doc — named to match the frontend's existing `AccountRole` type), `admin`.
Admin accounts aren't self-service — `POST /auth/signup` rejects `role: admin`.

## Social OAuth providers

`modules/auth/providers/` ports the OAuth handshake from the standalone
prototypes in `service-test/{tt,meta_fb,meta_insta,meta_threads}` — same
endpoints, same token-exchange steps, normalized into one `NormalizedToken`
shape. Only the *connect-an-account* step is ported here; each platform's
metrics/content endpoints (video list, Page posts, Threads insights, etc.)
belong to the Intelligence Engine module, not Auth.

- **tiktok** — PKCE required.
- **facebook**, **instagram**, **threads** — short-lived token → long-lived
  token exchange. No refresh-token flow ported yet; a token that's expired
  by the time `/internal/social-accounts/.../token` is called returns 409
  and the creator has to reconnect.
