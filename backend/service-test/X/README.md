# X (Twitter) metrics service

Small Flask app to validate Clippit's **Intelligence Engine** path for X:

1. **Connect** a creator account (official OAuth 2.0, or dev @handle mode)
2. **List posts** with view/like/reply counts
3. **Verify a submission URL** — confirm the tweet author matches the connected account and return metrics (what `/engine/verify` will do)

## Why two APIs?

| Concern | Provider | Notes |
|--------|----------|-------|
| **Identity** (who connected?) | Official [X API OAuth 2.0](https://docs.x.com/x-api/authentication/oauth-2-0/authorization-code) | PKCE flow, stores `@username` + user id |
| **Metrics** (views, likes) | [twitterapi.io](https://docs.twitterapi.io/introduction) | API key only, includes `viewCount` on tweets |

The official X API is expensive for read-heavy verification ($200+/mo Basic tier, strict rate limits). twitterapi.io is pay-as-you-go (~$0.15/1k tweets) and already exposes **view counts** — the core metric Clippit needs.

Production shape: OAuth in **Auth & Accounts**, metrics in **Intelligence Engine** using a server-side `TWITTERAPI_IO_KEY` (creators never see it).

## Quick start (dev mode — no X developer app)

```sh
cd backend/service-test/x
pip install -r requirements.txt
cp .env.example .env        # set TWITTERAPI_IO_KEY only
python service.py
```

Open http://127.0.0.1:8004 → enter an `@handle` → see posts + try **Engine verify**.

## Full OAuth setup

1. Create a project/app at [developer.x.com](https://developer.x.com/).
2. Enable **User authentication** → OAuth 2.0 → **Web App**.
3. Callback URL: `http://127.0.0.1:8004/callback` (must match `X_REDIRECT_URI`).
4. Scopes: `tweet.read`, `users.read`, `offline.access`.
5. Set `X_CLIENT_ID` and `X_CLIENT_SECRET` in `.env`.
6. Restart → **Connect X (OAuth)** on the page.

Free X developer tiers may be write-only; if OAuth read fails, use dev @handle mode to validate metrics while upgrading the X plan.

## Endpoints

| Route | Purpose |
|-------|---------|
| `/` | UI |
| `/login` | Start X OAuth 2.0 PKCE (when `X_CLIENT_ID` set) |
| `/callback` | OAuth redirect; stores user identity |
| `POST /api/dev-connect` | Dev-only: `{username}` → bind @handle without OAuth |
| `/api/config` | `{oauth_enabled}` |
| `/api/status` | `{connected, user}` |
| `/api/posts` | `{originals[], quotes[], retweets[], posts[]}` — `posts` = originals + quotes only (submittable) |
| `/api/verify?url=` | Engine sim: ownership check + `{metrics}` |
| `/api/replies?url=` | Reply tweets for a post (author, text, likes — fraud signals) |
| `/logout` | Clear session |

## Engine verify response

```json
{
  "verified": true,
  "owner_match": true,
  "expected_username": "creator",
  "author_username": "creator",
  "metrics": { "views": 12000, "likes": 340, "replies": 12, "retweets": 45, "quotes": 3 },
  "post": { "...": "normalized tweet" }
}
```

Paste any public `x.com/.../status/<id>` URL. The service parses the tweet id, fetches it from twitterapi.io, and checks `author.userName` against the connected account.

## Comments / replies (fraud detection)

Yes — twitterapi.io exposes reply tweets via `GET /twitter/tweet/replies` (also a v2 variant with sort options). Each reply includes **author username**, **text**, **like count**, **created time**, etc. Useful later for anomaly checks (bot replies, engagement ratio vs view count).

This prototype exposes that as `/api/replies?url=...`. The verify panel has a **Load sample replies** button (one extra API call, on demand).

Note: `reply_count` on the parent tweet (shown in verify metrics) is the total count; fetching individual replies is a separate, paginated call (~20 per page).

## What this proves for Clippit

- We can read **view counts** on X posts (paid metric on official API)
- We can **verify ownership** of a submission URL against a connected creator
- Cost model is predictable for the verification engine (per-tweet lookup, not per-creator OAuth read quota)

## Rate limits (429)

twitterapi.io throttles trial/low-tier keys aggressively. If you hit **429 Too Many Requests**:

- Wait ~30–60 seconds and click **Retry** (the service now auto-retries once with backoff)
- Avoid hammering **Refresh** — responses are cached for 60s
- `/api/posts` fetches **one page (20 tweets)** by default; add `?pages=3` only if you need more
- **Engine verify** (`/api/verify?url=...`) is the cheaper path for Clippit — one call per submission, not a full timeline scrape

## Not in scope (yet)

- OAuth provider port into `backend/modules/auth/providers/` (follow the TikTok pattern when ready)
- Video-only filtering rules for campaigns (UI flags `has_video` on posts today)
- Real-time monitoring webhooks (twitterapi.io stream — overkill for submission verify)
