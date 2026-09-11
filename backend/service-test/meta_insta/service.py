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

CLIENT_ID = os.environ.get("INSTAGRAM_APP_ID", "")
CLIENT_SECRET = os.environ.get("INSTAGRAM_APP_SECRET", "")
PORT = int(os.environ.get("PORT", "8001"))
REDIRECT_URI = os.environ.get("INSTAGRAM_REDIRECT_URI", f"https://localhost:{PORT}/callback")

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit("Set INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET in .env")

AUTH_URL = "https://api.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.instagram.com/access_token"
GRAPH_API = "https://graph.instagram.com/v22.0"
SCOPES = "instagram_business_basic,instagram_business_manage_insights"

USER_FIELDS = "user_id,username,name,account_type,profile_picture_url,followers_count,follows_count,media_count,biography"
MEDIA_FIELDS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"

INSIGHT_METRICS = {
    "IMAGE": ("views", "impressions", "reach", "saved"),
    "VIDEO": ("views", "impressions", "reach", "saved"),
    "REEL": ("views", "reach", "saved", "shares"),
    "CAROUSEL_ALBUM": ("views", "impressions", "reach", "saved"),
}

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET",
    hashlib.sha256(f"{CLIENT_ID}:{CLIENT_SECRET}:{REDIRECT_URI}".encode()).hexdigest(),
)


def store_session_token(access_token: str, user_id: str, expires_in: int = 0) -> None:
    session["token"] = {
        "access_token": access_token,
        "user_id": user_id,
        "expires_at": time.time() + expires_in if expires_in else 0,
    }


def get_access_token() -> str | None:
    token_data = session.get("token")
    return token_data["access_token"] if token_data else None


def get_user_id() -> str | None:
    token_data = session.get("token")
    return token_data["user_id"] if token_data else None


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
        return "Invalid OAuth state or missing code. Start over from /login.", 400

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

    ll_resp = requests.get(
        LONG_LIVED_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
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

    resp = requests.get(
        f"{GRAPH_API}/me",
        params={"fields": USER_FIELDS, "access_token": token},
        timeout=15,
    )
    data = resp.json()
    if "error" in data:
        return jsonify({"connected": False, "error": data["error"].get("message")})
    return jsonify({"connected": True, "user": data})


@app.route("/api/media")
def api_media():
    token = get_access_token()
    if not token:
        return jsonify({"error": "not connected"}), 401

    media_list = []
    url = f"{GRAPH_API}/me/media"
    params = {"fields": MEDIA_FIELDS, "limit": 50, "access_token": token}

    for _ in range(10):
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()
        if "error" in data:
            return jsonify({"error": data["error"].get("message")}), 400

        media_list.extend(data.get("data", []))
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}

    for item in media_list:
        media_type = item.get("media_type", "IMAGE")
        item["insights"] = fetch_insights(token, item["id"], media_type)

    total_views = sum(
        m.get("insights", {}).get("views", m.get("insights", {}).get("impressions", 0))
        for m in media_list
    )

    return jsonify({
        "count": len(media_list),
        "total_likes": sum(m.get("like_count", 0) for m in media_list),
        "total_comments": sum(m.get("comments_count", 0) for m in media_list),
        "total_views": total_views,
        "media": media_list,
    })


@app.route("/api/insights")
def api_insights():
    token = get_access_token()
    if not token:
        return jsonify({"error": "not connected"}), 401

    uid = get_user_id()
    if not uid:
        return jsonify({"error": "no user id"}), 400

    resp = requests.get(
        f"{GRAPH_API}/{uid}/insights",
        params={
            "metric": "reach,accounts_engaged,profile_views",
            "period": "day",
            "metric_type": "total_value",
            "since": int(time.time()) - 30 * 86400,
            "until": int(time.time()),
            "access_token": token,
        },
        timeout=20,
    )
    data = resp.json()
    if "error" in data:
        return jsonify({"error": data["error"].get("message")}), 400
    return jsonify({"insights": data.get("data", [])})


def fetch_insights(token: str, media_id: str, media_type: str) -> dict:
    metrics = INSIGHT_METRICS.get(media_type, INSIGHT_METRICS["IMAGE"])
    result = {}

    for metric in metrics:
        value = fetch_single_metric(token, media_id, metric)
        if value is not None:
            result[metric] = value

    if "views" not in result and "impressions" in result:
        result["views"] = result["impressions"]

    return result


def fetch_single_metric(token: str, media_id: str, metric: str) -> int | None:
    for attempt in range(2):
        try:
            resp = requests.get(
                f"{GRAPH_API}/{media_id}/insights",
                params={"metric": metric, "access_token": token},
                timeout=15,
            )
            data = resp.json()

            if "error" in data:
                if attempt < 1:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                return None

            data_items = data.get("data", [])
            if not data_items:
                return None

            values = data_items[0].get("values", [])
            if values:
                return values[0].get("value", 0)

            total_value = data_items[0].get("total_value", {})
            if isinstance(total_value, dict):
                return total_value.get("value", 0)

            return 0

        except Exception:
            if attempt < 1:
                time.sleep(0.5 * (2 ** attempt))
                continue
            return None

    return None


if __name__ == "__main__":
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes: {SCOPES}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
