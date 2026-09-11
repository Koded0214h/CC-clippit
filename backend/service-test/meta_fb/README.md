# Facebook Page metrics service

Small Flask app: connect a Facebook Page via OAuth (Facebook Login) and view
that page's posts and performance metrics.

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env        # fill in FACEBOOK_APP_ID / FACEBOOK_APP_SECRET
python service.py
```

Open http://localhost:8002 and click **Connect Facebook**.

## Meta portal config

1. Use the same Meta app you created for Instagram (Clipit), or create a new one.
2. Add **Facebook Login** as a product if not already added.
3. Under Facebook Login → Settings, add your redirect URI
   (must match `FACEBOOK_REDIRECT_URI` exactly).
4. For local dev, use a tunnel:

```sh
ngrok http 8002
# take the https URL it prints, then:
#  - register  https://<sub>.ngrok-free.app/callback  in the portal
#  - set FACEBOOK_REDIRECT_URI to the same value in .env
```

5. The Facebook account must manage at least one Facebook Page.

## Scopes

| Scope | Purpose |
| ----- | ------- |
| `pages_show_list` | List the user's Pages |
| `pages_read_engagement` | Post insights (impressions, reach, clicks) |
| `pages_read_user_content` | Read posts created by the Page |

## Endpoints

| Route | Purpose |
| ----- | ------- |
| `/` | The page |
| `/login` | Start Facebook OAuth |
| `/callback` | OAuth redirect; exchanges code for long-lived + page tokens |
| `/select-page/<id>` | Select which Page to view (if user manages multiple) |
| `/api/status` | `{connected, page_selected, page}` with page data |
| `/api/posts` | `{count, total_likes, total_comments, total_shares, total_impressions, total_reach, posts[]}` |
| `/api/page-insights` | Page-level insights (views, engagement, follows) |
| `/logout` | Clear the session |

## Notes

- Facebook uses a two-tier token system: **user token** (for auth) →
  **page token** (for all Page API calls).
- Page tokens derived from a long-lived user token don't expire.
- If the user manages multiple Pages, they'll see a selection screen after
  connecting.
- Post insights require `pages_read_engagement`. Some metrics were deprecated
  in Nov 2025 — the service uses the current replacement metrics.
- The app must be in Development mode with test users, OR go through App
  Review for production access.
