# TikTok video-views service

Small Flask app: connect a TikTok account via OAuth (Login Kit + Display API)
and list that account's videos with their view counts.

## Setup

```sh
pip install -r requirements.txt
cp .env.example .env        # fill in TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET
python service.py
```

Open http://localhost:8000 and click **Connect TikTok**.

## TikTok portal (Sandbox)

1. Create an app, switch to **Sandbox**.
2. Add products: **Login Kit** + **Display API**.
3. Add scopes: `user.info.basic`, `video.list`.
4. **Target Users**: add the `@handle` you'll test with (sandbox only allows
   whitelisted accounts).
5. **Redirect URI**: must match `TIKTOK_REDIRECT_URI` exactly.

TikTok rejects `http://localhost` for some apps. Tunnel instead:

```sh
ngrok http 8000
# take the https URL it prints, then:
#  - register  https://<sub>.ngrok-free.app/callback  in the portal
#  - set TIKTOK_REDIRECT_URI to the same value in .env
```

Free tunnel URLs change on every restart — re-register when that happens.

## Endpoints

| Route          | Purpose                                             |
| -------------- | --------------------------------------------------- |
| `/`            | The page                                            |
| `/login`       | Start OAuth (PKCE)                                  |
| `/callback`    | OAuth redirect target; exchanges code for token    |
| `/api/status`  | `{connected, user}`                                 |
| `/api/videos`  | `{count, total_views, videos[]}` for the account   |
| `/logout`      | Clear the session                                   |

## Notes

- Display API only exposes the **authorized user's own** videos. Arbitrary
  videos by URL need the Research API (approved researchers only).
- Access tokens are kept in the Flask session and auto-refreshed.
