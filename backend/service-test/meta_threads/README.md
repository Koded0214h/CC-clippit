# Threads metrics service

Small Flask app: connect a Threads account via OAuth and view that account's
posts and performance metrics.

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env        # fill in THREADS_APP_ID / THREADS_APP_SECRET
python service.py
```

Open http://localhost:8003 and click **Connect Threads**.

## Meta portal config

1. Use the same Meta app (Clipit), or create a new one at developers.facebook.com.
2. Add **Access the Threads API** as a product (from the dashboard → Available products).
3. Under the Threads product settings, add your redirect URI
   (must match `THREADS_REDIRECT_URI` exactly).
4. For local dev, use a tunnel:

```sh
ngrok http 8003
# take the https URL it prints, then:
#  - register  https://<sub>.ngrok-free.app/callback  in the portal
#  - set THREADS_REDIRECT_URI to the same value in .env
```

5. Add your Threads account as a tester under App Roles → Roles
   (required while the app is in Development mode).

## Important: Threads uses its own API host

Threads does NOT use `graph.facebook.com` or `graph.instagram.com`.
It has its own:
- **OAuth:** `threads.net/oauth/authorize`
- **API:** `graph.threads.net/v1.0`

## Scopes

| Scope | Purpose |
| ----- | ------- |
| `threads_basic` | Profile info, threads list (required) |
| `threads_manage_insights` | Views, likes, replies, reposts, quotes per thread |
| `threads_read_replies` | Read reply threads |

## Endpoints

| Route | Purpose |
| ----- | ------- |
| `/` | The page |
| `/login` | Start Threads OAuth |
| `/callback` | OAuth redirect; exchanges code for long-lived token |
| `/api/status` | `{connected, user}` with profile data |
| `/api/threads` | `{count, total_views, total_likes, total_replies, total_reposts, total_quotes, threads[]}` |
| `/api/user-insights` | User-level aggregate insights |
| `/logout` | Clear the session |

## Available metrics per thread

| Metric | Description |
| ------ | ----------- |
| `views` | Number of times the thread was displayed |
| `likes` | Total likes |
| `replies` | Number of replies |
| `reposts` | Total reposts |
| `quotes` | Total quote posts |

## Notes

- Short-lived tokens (1 hour) are automatically exchanged for long-lived
  tokens (60 days) during the callback using `th_exchange_token`.
- Long-lived tokens can be refreshed via `th_refresh_token` before they
  expire (the service doesn't do this yet — for the test it's fine).
- Thread insights are fetched per-post. For accounts with many threads this
  can be slow on first load.
- The Threads API has rate limits tied to account impressions. Check
  `/{user-id}/threads_publishing_limit` if you hit limits.
- The app must be in Development mode with test users, OR go through App
  Review + Tech Provider Verification for production access.
