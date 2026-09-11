"""Minimal Facebook Page metrics service.

Flow:
  1. User clicks "Connect Facebook" -> /login -> Facebook OAuth consent
  2. Facebook redirects to /callback with a code
  3. We exchange the code for a short-lived user token
  4. Exchange for a long-lived user token (60 days)
  5. Fetch the user's Pages via /me/accounts to get Page access tokens
  6. /api/posts pulls the Page's posts + their metrics

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your Facebook app credentials
    python service.py
    open http://localhost:8002

FACEBOOK_REDIRECT_URI must be registered in the Meta developer portal under
your app's Facebook Login config, exactly as sent.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, request, send_from_directory, session

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env_file() -> None:
    env_path = os.path.join(HERE, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env_file()

CLIENT_ID = os.environ.get("FACEBOOK_APP_ID", "")
CLIENT_SECRET = os.environ.get("FACEBOOK_APP_SECRET", "")
PORT = int(os.environ.get("PORT", "8002"))
REDIRECT_URI = os.environ.get(
    "FACEBOOK_REDIRECT_URI", f"https://localhost:{PORT}/callback"
)

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit("Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in .env")

GRAPH_VERSION = "v22.0"
AUTH_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
TOKEN_URL = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
GRAPH_API = f"https://graph.facebook.com/{GRAPH_VERSION}"

SCOPES = "pages_show_list,pages_read_engagement,pages_read_user_content"

PAGE_FIELDS = ",".join([
    "id",
    "name",
    "category",
    "fan_count",
    "followers_count",
    "picture{url}",
    "cover{source}",
    "about",
    "website",
    "link",
])

POST_FIELDS = ",".join([
    "id",
    "message",
    "created_time",
    "full_picture",
    "permalink_url",
    "shares",
    "likes.summary(true).limit(0)",
    "comments.summary(true).limit(0)",
    "type",
    "status_type",
])

POST_INSIGHT_METRICS = "post_impressions,post_impressions_unique,post_clicks"

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET",
    hashlib.sha256(f"{CLIENT_ID}:{CLIENT_SECRET}:{REDIRECT_URI}".encode()).hexdigest(),
)


# --- Session helpers --------------------------------------------------------
def store_session_token(
    user_token: str, user_id: str, expires_in: int = 0
) -> None:
    session["token"] = {
        "user_token": user_token,
        "access_token": user_token,
        "user_id": user_id,
        "expires_at": time.time() + expires_in if expires_in else 0,
    }


def get_user_token() -> str | None:
    tok = session.get("token")
    if not tok:
        return None
    return tok.get("user_token") or tok.get("access_token")


def get_page_token() -> str | None:
    page = session.get("page")
    return page["access_token"] if page else None


def get_page_id() -> str | None:
    page = session.get("page")
    return page["id"] if page else None


# --- Routes -----------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/login")
def login():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@app.route("/callback")
def callback():
    if request.args.get("error"):
        desc = request.args.get("error_description", request.args["error"])
        return f"Authorization failed: {desc}", 400
    if (
        not request.args.get("code")
        or request.args.get("state") != session.get("oauth_state")
    ):
        return "Invalid OAuth state or missing code.", 400

    # Step 1: Exchange code for short-lived user token
    resp = requests.get(
        TOKEN_URL,
        params={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": request.args["code"],
        },
        timeout=15,
    )
    payload = resp.json()
    if "access_token" not in payload:
        return f"Token exchange failed: {payload}", 400

    short_token = payload["access_token"]

    # Step 2: Exchange for long-lived user token (60 days)
    ll_resp = requests.get(
        TOKEN_URL,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    ll_payload = ll_resp.json()
    user_token = ll_payload.get("access_token", short_token)
    expires_in = int(ll_payload.get("expires_in", 5184000))

    # Get user ID
    me_resp = requests.get(
        f"{GRAPH_API}/me",
        params={"access_token": user_token},
        timeout=10,
    )
    user_id = me_resp.json().get("id", "")

    store_session_token(user_token, user_id, expires_in)

    # Step 3: Fetch Pages the user manages
    pages_resp = requests.get(
        f"{GRAPH_API}/me/accounts",
        params={
            "fields": "id,name,access_token,category,picture{url}",
            "access_token": user_token,
        },
        timeout=15,
    )
    pages_data = pages_resp.json().get("data", [])
    session["pages"] = pages_data

    # Auto-select first page if only one
    if len(pages_data) == 1:
        session["page"] = pages_data[0]

    return redirect("/")


@app.route("/select-page/<page_id>")
def select_page(page_id):
    pages = session.get("pages", [])
    for p in pages:
        if p["id"] == page_id:
            session["page"] = p
            break
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/api/status")
def api_status():
    user_token = get_user_token()
    if not user_token:
        return jsonify({"connected": False})

    pages = session.get("pages", [])
    selected = session.get("page")

    if not selected:
        # Connected to Facebook but no page selected yet
        return jsonify({
            "connected": True,
            "page_selected": False,
            "pages": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "category": p.get("category", ""),
                    "picture_url": p.get("picture", {}).get("data", {}).get("url", ""),
                }
                for p in pages
            ],
        })

    # Fetch full page info
    page_token = selected["access_token"]
    resp = requests.get(
        f"{GRAPH_API}/{selected['id']}",
        params={"fields": PAGE_FIELDS, "access_token": page_token},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        return jsonify({"connected": False, "error": data["error"].get("message")})

    # Flatten picture
    pic = data.get("picture", {}).get("data", {}).get("url", "")
    data["picture_url"] = pic
    cover = data.get("cover", {}).get("source", "")
    data["cover_url"] = cover

    return jsonify({"connected": True, "page_selected": True, "page": data})


@app.route("/api/posts")
def api_posts():
    page_token = get_page_token()
    page_id = get_page_id()
    if not page_token or not page_id:
        return jsonify({"error": "not connected or no page selected"}), 401

    posts_list = []
    url = f"{GRAPH_API}/{page_id}/posts"
    params = {"fields": POST_FIELDS, "limit": 50, "access_token": page_token}

    for _ in range(10):
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()
        if "error" in data:
            return jsonify({"error": data["error"].get("message")}), 400
        posts_list.extend(data.get("data", []))
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}

    # Fetch insights for each post
    for post in posts_list:
        post["insights"] = fetch_post_insights(page_token, post["id"])
        # Flatten likes/comments/shares counts
        post["like_count"] = post.get("likes", {}).get("summary", {}).get("total_count", 0)
        post["comment_count"] = post.get("comments", {}).get("summary", {}).get("total_count", 0)
        post["share_count"] = post.get("shares", {}).get("count", 0)

    total_likes = sum(p.get("like_count", 0) for p in posts_list)
    total_comments = sum(p.get("comment_count", 0) for p in posts_list)
    total_shares = sum(p.get("share_count", 0) for p in posts_list)
    total_impressions = sum(
        p.get("insights", {}).get("post_impressions", 0) for p in posts_list
    )
    total_reach = sum(
        p.get("insights", {}).get("post_impressions_unique", 0) for p in posts_list
    )

    return jsonify({
        "count": len(posts_list),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_impressions": total_impressions,
        "total_reach": total_reach,
        "posts": posts_list,
    })


@app.route("/api/page-insights")
def api_page_insights():
    """Page-level insights for the last 30 days."""
    page_token = get_page_token()
    page_id = get_page_id()
    if not page_token or not page_id:
        return jsonify({"error": "not connected or no page selected"}), 401

    resp = requests.get(
        f"{GRAPH_API}/{page_id}/insights",
        params={
            "metric": "page_views_total,page_engaged_users,page_post_engagements,page_daily_follows",
            "period": "day",
            "since": int(time.time()) - 30 * 86400,
            "until": int(time.time()),
            "access_token": page_token,
        },
        timeout=20,
    )
    data = resp.json()
    if "error" in data:
        return jsonify({"error": data["error"].get("message")}), 400
    return jsonify({"insights": data.get("data", [])})


def fetch_post_insights(page_token: str, post_id: str) -> dict:
    """Fetch insights for a single post. Returns a flat dict of metric:value."""
    try:
        resp = requests.get(
            f"{GRAPH_API}/{post_id}/insights",
            params={
                "metric": POST_INSIGHT_METRICS,
                "access_token": page_token,
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            return {}
        result = {}
        for metric in data.get("data", []):
            name = metric.get("name", "")
            values = metric.get("values", [{}])
            result[name] = values[0].get("value", 0) if values else 0
        return result
    except Exception:
        return {}


if __name__ == "__main__":
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes: {SCOPES}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
