"""Minimal Threads metrics service.

Flow:
  1. User clicks "Connect Threads" -> /login -> Threads OAuth consent
  2. Threads redirects to /callback with a code
  3. We exchange the code for a short-lived token, then swap for a long-lived token
  4. /api/threads pulls the connected user's posts + their metrics

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your Threads app credentials
    python service.py
    open http://localhost:8003

THREADS_REDIRECT_URI must be registered in the Meta developer portal under
your app's Threads config, exactly as sent. Threads requires HTTPS for
redirect URIs -- use an https tunnel (ngrok / cloudflared) and set
THREADS_REDIRECT_URI to that public https URL + /callback.
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

CLIENT_ID = os.environ.get("THREADS_APP_ID", "")
CLIENT_SECRET = os.environ.get("THREADS_APP_SECRET", "")
PORT = int(os.environ.get("PORT", "8003"))
REDIRECT_URI = os.environ.get(
    "THREADS_REDIRECT_URI", f"https://localhost:{PORT}/callback"
)

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit("Set THREADS_APP_ID and THREADS_APP_SECRET in .env")

# Threads OAuth endpoints
AUTH_URL = "https://threads.net/oauth/authorize"
TOKEN_URL = "https://graph.threads.net/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.threads.net/access_token"

# Threads Graph API
GRAPH_API = "https://graph.threads.net/v1.0"

SCOPES = "threads_basic,threads_manage_insights,threads_read_replies"

USER_FIELDS = ",".join([
    "id",
    "username",
    "name",
    "threads_profile_picture_url",
    "threads_biography",
    "is_verified",
])

THREAD_FIELDS = ",".join([
    "id",
    "text",
    "media_type",
    "media_url",
    "permalink",
    "timestamp",
    "is_quote_status",
    "shortcode",
])

INSIGHT_METRICS = "views,likes,replies,reposts,quotes"

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET",
    hashlib.sha256(f"{CLIENT_ID}:{CLIENT_SECRET}:{REDIRECT_URI}".encode()).hexdigest(),
)


# --- Session helpers --------------------------------------------------------
def store_session_token(access_token: str, user_id: str, expires_in: int = 0) -> None:
    session["token"] = {
        "access_token": access_token,
        "user_id": user_id,
        "expires_at": time.time() + expires_in if expires_in else 0,
    }


def get_access_token() -> str | None:
    tok = session.get("token")
    return tok["access_token"] if tok else None


def get_user_id() -> str | None:
    tok = session.get("token")
    return tok["user_id"] if tok else None


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

    # Step 1: Exchange code for short-lived token
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": request.args["code"],
        },
        timeout=15,
    )
    payload = resp.json()
    if "access_token" not in payload:
        return f"Token exchange failed: {payload}", 400

    short_token = payload["access_token"]
    user_id = str(payload.get("user_id", ""))

    # Step 2: Exchange short-lived token for long-lived token (60 days)
    ll_resp = requests.get(
        LONG_LIVED_TOKEN_URL,
        params={
            "grant_type": "th_exchange_token",
            "client_secret": CLIENT_SECRET,
            "access_token": short_token,
        },
        timeout=15,
    )
    ll_payload = ll_resp.json()
    if "access_token" in ll_payload:
        store_session_token(
            ll_payload["access_token"],
            user_id,
            int(ll_payload.get("expires_in", 5184000)),
        )
    else:
        # Fall back to short-lived token
        store_session_token(short_token, user_id, 3600)

    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/api/status")
def api_status():
    token = get_access_token()
    if not token:
        return jsonify({"connected": False})

    uid = get_user_id()
    if not uid:
        return jsonify({"connected": False, "error": "No user ID"})

    resp = requests.get(
        f"{GRAPH_API}/{uid}",
        params={"fields": USER_FIELDS, "access_token": token},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        return jsonify({"connected": False, "error": data["error"].get("message")})
    return jsonify({"connected": True, "user": data})


@app.route("/api/threads")
def api_threads():
    token = get_access_token()
    uid = get_user_id()
    if not token or not uid:
        return jsonify({"error": "not connected"}), 401

    threads_list = []
    url = f"{GRAPH_API}/{uid}/threads"
    params = {"fields": THREAD_FIELDS, "limit": 50, "access_token": token}

    # Paginate through threads (up to 10 pages = ~500 posts)
    for _ in range(10):
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()
        if "error" in data:
            return jsonify({"error": data["error"].get("message")}), 400
        threads_list.extend(data.get("data", []))
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}

    # Fetch insights for each thread
    for item in threads_list:
        item["insights"] = fetch_thread_insights(token, item["id"])

    total_views = sum(t.get("insights", {}).get("views", 0) for t in threads_list)
    total_likes = sum(t.get("insights", {}).get("likes", 0) for t in threads_list)
    total_replies = sum(t.get("insights", {}).get("replies", 0) for t in threads_list)
    total_reposts = sum(t.get("insights", {}).get("reposts", 0) for t in threads_list)
    total_quotes = sum(t.get("insights", {}).get("quotes", 0) for t in threads_list)

    return jsonify({
        "count": len(threads_list),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_replies": total_replies,
        "total_reposts": total_reposts,
        "total_quotes": total_quotes,
        "threads": threads_list,
    })


@app.route("/api/user-insights")
def api_user_insights():
    """User-level insights (follower demographics, etc.)."""
    token = get_access_token()
    uid = get_user_id()
    if not token or not uid:
        return jsonify({"error": "not connected"}), 401

    resp = requests.get(
        f"{GRAPH_API}/{uid}/threads_insights",
        params={
            "metric": "views,likes,replies,reposts,quotes,followers_count",
            "access_token": token,
        },
        timeout=20,
    )
    data = resp.json()
    if "error" in data:
        return jsonify({"error": data["error"].get("message")}), 400
    return jsonify({"insights": data.get("data", [])})


def fetch_thread_insights(token: str, thread_id: str) -> dict:
    """Fetch insights for a single thread. Returns a flat dict of metric:value."""
    try:
        resp = requests.get(
            f"{GRAPH_API}/{thread_id}/insights",
            params={"metric": INSIGHT_METRICS, "access_token": token},
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            return {}
        result = {}
        for metric in data.get("data", []):
            name = metric.get("name", "")
            values = metric.get("values", [{}])
            if values:
                result[name] = values[0].get("value", 0)
            else:
                total = metric.get("total_value", {})
                result[name] = total.get("value", 0) if isinstance(total, dict) else 0
        return result
    except Exception:
        return {}


if __name__ == "__main__":
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes: {SCOPES}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
