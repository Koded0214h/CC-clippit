"""Minimal TikTok "video views" service.

Flow:
  1. User clicks "Connect TikTok" -> /login -> TikTok OAuth consent
  2. TikTok redirects to /callback with a code
  3. We exchange the code for an access token (scope: user.info.basic, video.list)
  4. /api/videos pulls the connected user's videos + their view_count

Run:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in your sandbox client key/secret
    python service.py
    open http://localhost:8000

TIKTOK_REDIRECT_URI must be registered in the TikTok developer portal under
your app's Login Kit config, exactly as sent. TikTok rejects http://localhost
for some apps -- use an https tunnel (ngrok / cloudflared) and set
TIKTOK_REDIRECT_URI to that public https URL + /callback.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, request, send_from_directory, session

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a local .env file into os.environ."""
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()

# --- Config -----------------------------------------------------------------
# All secrets come from the environment. Copy .env.example to .env and fill it
# in, or export these before running. Nothing sensitive is committed.
CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
PORT = int(os.environ.get("PORT", "8000"))
REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", f"http://localhost:{PORT}/callback")
SCOPES = "user.info.basic,video.list"

if not CLIENT_KEY or not CLIENT_SECRET:
    raise SystemExit(
        "Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET (see .env.example)."
    )

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"

VIDEO_FIELDS = ",".join(
    [
        "id",
        "title",
        "video_description",
        "cover_image_url",
        "share_url",
        "create_time",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
    ]
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(16))


# --- OAuth helpers ---------------------------------------------------------
def _store_token(payload: dict) -> None:
    session["token"] = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "open_id": payload.get("open_id"),
        "expires_at": time.time() + int(payload.get("expires_in", 0)),
    }


def _refresh_token(refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _access_token() -> str | None:
    tok = session.get("token")
    if not tok:
        return None
    if time.time() > tok["expires_at"] - 60:
        if not tok.get("refresh_token"):
            session.pop("token", None)
            return None
        _store_token(_refresh_token(tok["refresh_token"]))
        tok = session["token"]
    return tok["access_token"]


def _api_error(resp_json: dict) -> str | None:
    err = resp_json.get("error") or {}
    code = err.get("code")
    if code and code != "ok":
        return f"{code}: {err.get('message', 'unknown error')}"
    return None


# --- Routes --------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/login")
def login():
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    session["oauth_state"] = state
    session["code_verifier"] = verifier
    params = {
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@app.route("/callback")
def callback():
    if request.args.get("error"):
        return f"Authorization failed: {request.args.get('error_description', request.args['error'])}", 400
    if not request.args.get("code") or request.args.get("state") != session.get("oauth_state"):
        return "Invalid OAuth state or missing code.", 400

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": request.args["code"],
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": session.get("code_verifier", ""),
        },
        timeout=15,
    )
    payload = resp.json()
    if "access_token" not in payload:
        return f"Token exchange failed: {payload}", 400
    _store_token(payload)
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/api/status")
def api_status():
    token = _access_token()
    if not token:
        return jsonify({"connected": False})

    resp = requests.get(
        USER_INFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "open_id,display_name,avatar_url"},
        timeout=15,
    )
    data = resp.json()
    if _api_error(data):
        return jsonify({"connected": False, "error": _api_error(data)})
    return jsonify({"connected": True, "user": data.get("data", {}).get("user", {})})


@app.route("/api/videos")
def api_videos():
    token = _access_token()
    if not token:
        return jsonify({"error": "not connected"}), 401

    videos: list[dict] = []
    cursor = 0
    for _ in range(10):  # up to ~200 videos
        resp = requests.post(
            VIDEO_LIST_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params={"fields": VIDEO_FIELDS},
            json={"max_count": 20, "cursor": cursor},
            timeout=20,
        )
        data = resp.json()
        err = _api_error(data)
        if err:
            return jsonify({"error": err}), 400
        block = data.get("data", {})
        videos.extend(block.get("videos", []))
        if not block.get("has_more"):
            break
        cursor = block.get("cursor", 0)

    total_views = sum(v.get("view_count", 0) for v in videos)
    videos.sort(key=lambda v: v.get("view_count", 0), reverse=True)
    return jsonify({"count": len(videos), "total_views": total_views, "videos": videos})


if __name__ == "__main__":
    print(f" * Redirect URI (add this in the portal): {REDIRECT_URI}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
