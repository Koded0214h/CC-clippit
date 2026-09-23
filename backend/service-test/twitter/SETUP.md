# X / Twitter Metrics — Setup Guide

---

## 1. Create a Developer App

1. Go to https://developer.twitter.com/en/portal/dashboard
2. Sign in with the X account you want to pull data from
3. Click **"+ Create Project"** → give it any name (e.g. Clippit)
4. Choose use case → **"Making a bot"** or **"Building tools for my own use"**
5. Inside the project click **"+ Add App"** → name it anything
6. On the app's **"Keys and tokens"** tab, copy and save:
   - **Client ID**
   - **Client Secret**
   - **Bearer Token** (not needed for this flow but save it anyway)

---

## 2. Configure User Authentication (OAuth 2.0)

Inside your app on the developer portal:

1. Click **"Edit"** next to **User authentication settings**
2. Fill in:

| Field | Value |
|---|---|
| OAuth 2.0 | **On** |
| Type of App | **Web App, Automated App or Bot** |
| Callback / Redirect URI | `http://localhost:5000/callback` |
| Website URL | `http://localhost:5000` |

3. Click **Save**

---

## 3. Install Python Dependencies

Open a terminal in the `twitter/` folder and run:

```bash
pip install flask requests requests-oauthlib
```

---

## 4. Create `service.py`

Create a file called `service.py` in the same folder as `index.html` with this content:

```python
import os, json, secrets
from flask import Flask, redirect, request, session, jsonify
import requests
from requests_oauthlib import OAuth2Session

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(16))

CLIENT_ID     = os.environ["TWITTER_CLIENT_ID"]
CLIENT_SECRET = os.environ["TWITTER_CLIENT_SECRET"]
REDIRECT_URI  = "http://localhost:5000/callback"

AUTH_URL  = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
SCOPES    = ["tweet.read", "users.read", "offline.access"]


def twitter_session():
    return OAuth2Session(
        CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        token=session.get("token"),
    )


# --- Auth -------------------------------------------------------------------

@app.route("/login")
def login():
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES)
    url, state = oauth.authorization_url(AUTH_URL, code_challenge_method="S256")
    session["oauth_state"] = state
    return redirect(url)


@app.route("/callback")
def callback():
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI,
                          state=session.get("oauth_state"))
    token = oauth.fetch_token(
        TOKEN_URL,
        client_secret=CLIENT_SECRET,
        authorization_response=request.url,
        include_client_id=True,
    )
    session["token"] = token
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# --- API --------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    if "token" not in session:
        return jsonify(connected=False)
    try:
        oauth = twitter_session()
        r = oauth.get(
            "https://api.twitter.com/2/users/me",
            params={
                "user.fields": "id,name,username,description,location,"
                               "profile_image_url,verified,public_metrics"
            },
        )
        if r.status_code == 401:
            session.clear()
            return jsonify(connected=False, error="Session expired — please reconnect.")
        r.raise_for_status()
        user = r.json().get("data", {})
        session["user_id"] = user.get("id")
        return jsonify(connected=True, user=user)
    except Exception as e:
        return jsonify(connected=False, error=str(e))


@app.route("/api/tweets")
def api_tweets():
    if "token" not in session:
        return jsonify(error="Not authenticated"), 401

    oauth = twitter_session()

    # Resolve user id
    user_id = session.get("user_id")
    if not user_id:
        me = oauth.get(
            "https://api.twitter.com/2/users/me",
            params={"user.fields": "id"},
        ).json().get("data", {})
        user_id = me.get("id")
    if not user_id:
        return jsonify(error="Could not resolve user ID"), 500

    r = oauth.get(
        f"https://api.twitter.com/2/users/{user_id}/tweets",
        params={
            "max_results": 100,
            "tweet.fields": "id,text,created_at,public_metrics,referenced_tweets",
            "expansions": "referenced_tweets.id",
        },
    )
    r.raise_for_status()
    tweets = r.json().get("data") or []

    total_impressions = 0
    total_likes       = 0
    total_retweets    = 0
    total_replies     = 0

    for t in tweets:
        pm = t.get("public_metrics", {})
        total_impressions += pm.get("impression_count", 0)
        total_likes       += pm.get("like_count", 0)
        total_retweets    += pm.get("retweet_count", 0)
        total_replies     += pm.get("reply_count", 0)
        t["permalink"] = f"https://x.com/i/web/status/{t['id']}"

    return jsonify(
        tweets=tweets,
        count=len(tweets),
        total_impressions=total_impressions,
        total_likes=total_likes,
        total_retweets=total_retweets,
        total_replies=total_replies,
    )


@app.route("/api/insights")
def api_insights():
    # No separate analytics endpoint on free tier.
    # Extend this later if you upgrade to Basic ($100/mo).
    return jsonify(metrics=[])


# Serve frontend for all non-API routes
@app.route("/")
@app.route("/<path:path>")
def serve(path="index.html"):
    return app.send_static_file("index.html")


if __name__ == "__main__":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # localhost only, never production
    app.run(debug=True, port=5000)
```

---

## 5. Set Environment Variables and Run

Open PowerShell in the `twitter/` folder:

```powershell
$env:TWITTER_CLIENT_ID     = "paste_your_client_id_here"
$env:TWITTER_CLIENT_SECRET = "paste_your_client_secret_here"
$env:FLASK_SECRET          = "any_random_string_you_make_up"
python service.py
```

Then open your browser at:

```
http://localhost:5000
```

Click **Connect X Account**, authorize, and your metrics will load.

---

## 6. What Data Comes Back (and Where It Shows in the UI)

### `/api/status` → user profile card + follower counts

The Twitter API returns this shape under `data`:

```json
{
  "id": "123456",
  "name": "Display Name",
  "username": "handle",
  "description": "Bio text",
  "location": "Lagos",
  "profile_image_url": "https://...",
  "verified": false,
  "public_metrics": {
    "followers_count": 4200,
    "following_count": 310,
    "tweet_count": 980,
    "listed_count": 12
  }
}
```

### `/api/tweets` → tweet table

Each tweet in the `tweets` array:

```json
{
  "id": "1234567890",
  "text": "Tweet content here",
  "created_at": "2025-09-01T14:22:00Z",
  "permalink": "https://x.com/i/web/status/1234567890",
  "referenced_tweets": [
    { "type": "retweeted", "id": "..." }
  ],
  "public_metrics": {
    "impression_count": 8400,
    "like_count": 210,
    "retweet_count": 44,
    "reply_count": 17,
    "quote_count": 5,
    "bookmark_count": 31
  }
}
```

`referenced_tweets[].type` can be `retweeted`, `replied_to`, or `quoted`.
The frontend uses this to badge each tweet as TWEET / RETWEET / REPLY / QUOTE.

### `/api/insights` → account-level metrics strip (optional)

```json
{
  "metrics": [
    { "name": "profile_visits", "value": 14200 },
    { "name": "link_clicks",    "value": 830 }
  ]
}
```

Return an empty array `[]` if you have nothing to show. The frontend hides the strip automatically.

---

## 7. Important Limits (Free Tier)

| What | Limit |
|---|---|
| Tweets you can read per month | 500,000 |
| `impression_count` available | Only on **your own** tweets via OAuth 2.0 |
| Historical tweets per call | Max 100 (use pagination `next_token` for more) |
| Account analytics endpoint | Not available on free tier |

To get more analytics (engagement rate, profile visits, etc.) you need the **Basic** plan at $100/month from the developer portal.

---

## 8. File Structure When Done

```
twitter/
  index.html    ← frontend (already written)
  service.py    ← backend you write from section 4
  SETUP.md      ← this file
```
