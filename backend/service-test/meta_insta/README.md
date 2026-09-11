# Instagram metrics service

Small Flask app: connect an Instagram Business/Creator account via OAuth
(Instagram Login for Business) and view that account's profile, posts, and
performance metrics.

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env        # fill in INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET
python service.py
```

Open http://localhost:8001 and click **Connect Instagram**.

## Meta portal config

1. Create an app at developers.facebook.com, add the **Instagram** product.
2. Under "API setup with Instagram business login" → Step 3 → **Set up**,
   add your redirect URI (must match `INSTAGRAM_REDIRECT_URI` exactly).
3. Instagram requires HTTPS for redirect URIs. For local dev, use a tunnel:

```sh
ngrok http 8001
# take the https URL it prints, then:
#  - register  https://<sub>.ngrok-free.app/callback  in the portal
#  - set INSTAGRAM_REDIRECT_URI to the same value in .env
```

4. Under App roles → Test users, add the Instagram account you'll test with
   (required while the app is in Development mode).
5. The Instagram account must be a **Business** or **Creator** account.

## Scopes

| Scope | Purpose |
| ----- | ------- |
| `instagram_business_basic` | Profile, media list, like/comment counts |
| `instagram_business_manage_insights` | Reach, views, saved, per-post insights |

## Endpoints

| Route | Purpose |
| ----- | ------- |
| `/` | The page |
| `/login` | Start OAuth |
| `/callback` | OAuth redirect target; exchanges code for long-lived token |
| `/api/status` | `{connected, user}` with profile data |
| `/api/media` | `{count, total_likes, total_comments, total_views, media[]}` |
| `/api/insights` | Account-level insights (reach, engagement, profile views) |
| `/logout` | Clear the session |

## Notes

- Short-lived tokens (1 hour) are automatically exchanged for long-lived
  tokens (60 days) during the callback.
- Media insights are fetched per-post. For accounts with many posts this
  can be slow on first load — pagination caps at ~500 posts.
- Account-level insights require at least 100 followers.
- The app must be in Development mode with test users, OR go through App
  Review for production access.
