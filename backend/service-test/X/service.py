"""Minimal X (Twitter) metrics service for Clippit engine validation.

Flow:
  1. User clicks "Connect X" -> /login -> X OAuth 2.0 consent (when configured)
     OR enters @handle in dev mode (no OAuth credentials)
  2. X redirects to /callback with a code; we exchange for an access token
  3. /api/posts pulls the connected user's recent posts + view/like counts
     via twitterapi.io (not the official X API — cheaper, includes viewCount)
  4. /api/verify?url=... simulates the Intelligence Engine: parse a submission
     URL, fetch metrics, confirm the author matches the connected account

Run:
    pip install -r requirements.txt
    cp .env.example .env   # TWITTERAPI_IO_KEY required; X OAuth optional
    python service.py
    open http://localhost:8004

Metrics use https://docs.twitterapi.io (API key only).
Identity uses official X OAuth 2.0 PKCE when X_CLIENT_ID is set:
https://docs.x.com/x-api/authentication/oauth-2-0/authorization-code
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import time
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, request, send_from_directory, session

HERE = os.path.dirname(os.path.abspath(__file__))

TWEET_ID_RE = re.compile(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)", re.I)
STATUS_ID_RE = re.compile(r"/status/(\d+)")


def _load_dotenv() -> None:
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
TWITTERAPI_IO_KEY = os.environ.get("TWITTERAPI_IO_KEY", "")
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
PORT = int(os.environ.get("PORT", "8004"))
REDIRECT_URI = os.environ.get("X_REDIRECT_URI", f"http://127.0.0.1:{PORT}/callback")
SCOPES = "tweet.read users.read offline.access"

if not TWITTERAPI_IO_KEY:
    raise SystemExit("Set TWITTERAPI_IO_KEY (sign up at https://twitterapi.io).")

OAUTH_ENABLED = bool(X_CLIENT_ID)

# Official X OAuth 2.0
X_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
X_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
X_USER_ME_URL = "https://api.twitter.com/2/users/me"

# twitterapi.io read endpoints
IO_BASE = "https://api.twitterapi.io"
IO_HEADERS = {"x-api-key": TWITTERAPI_IO_KEY}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(16))


# --- twitterapi.io helpers --------------------------------------------------
class IoRateLimited(RuntimeError):
    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__(
            "twitterapi.io rate limit hit — wait a minute and retry, "
            "or upgrade your plan for higher QPS."
        )


def _extract_tweets(payload: dict) -> list[dict]:
    """twitterapi.io nests tweets differently per endpoint."""
    tweets = payload.get("tweets")
    if tweets:
        return tweets
    inner = payload.get("data")
    if isinstance(inner, dict):
        return inner.get("tweets") or inner.get("replies") or []
    if isinstance(inner, list):
        return inner
    return payload.get("replies") or []


def _io_get(path: str, params: dict | None = None, *, retries: int = 3) -> dict:
    last_rate_limit: IoRateLimited | None = None
    for attempt in range(retries):
        resp = requests.get(
            f"{IO_BASE}{path}",
            headers=IO_HEADERS,
            params=params or {},
            timeout=30,
        )
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            last_rate_limit = IoRateLimited(retry_after=wait)
            if attempt < retries - 1:
                time.sleep(min(wait, 8))
                continue
            raise last_rate_limit
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error":
            raise RuntimeError(data.get("message") or data.get("msg") or "twitterapi.io error")
        return data
    if last_rate_limit:
        raise last_rate_limit
    raise RuntimeError("twitterapi.io request failed")


def _classify_post_type(raw: dict) -> str:
    if raw.get("retweeted_tweet"):
        return "retweet"
    if raw.get("quoted_tweet"):
        return "quote"
    if raw.get("isReply"):
        return "reply"
    return "original"


def _normalize_tweet(raw: dict) -> dict:
    author = raw.get("author") or {}
    post_type = _classify_post_type(raw)
    quoted = raw.get("quoted_tweet") or {}
    retweeted = raw.get("retweeted_tweet") or {}
    media = []
    for ent in (raw.get("extendedEntities") or {}).get("media", []):
        media.append(
            {
                "type": ent.get("type"),
                "url": ent.get("media_url_https") or ent.get("url"),
                "preview": ent.get("media_url_https"),
            }
        )
    if not media:
        for ent in (raw.get("entities") or {}).get("media", []):
            media.append(
                {
                    "type": ent.get("type"),
                    "url": ent.get("media_url_https") or ent.get("expanded_url"),
                    "preview": ent.get("media_url_https"),
                }
            )

    return {
        "id": raw.get("id"),
        "url": raw.get("url"),
        "text": raw.get("text", ""),
        "post_type": post_type,
        "submittable": post_type in {"original", "quote"},
        "view_count": raw.get("viewCount") or 0,
        "like_count": raw.get("likeCount") or 0,
        "reply_count": raw.get("replyCount") or 0,
        "retweet_count": raw.get("retweetCount") or 0,
        "quote_count": raw.get("quoteCount") or 0,
        "bookmark_count": raw.get("bookmarkCount") or 0,
        "created_at": raw.get("createdAt"),
        "is_reply": raw.get("isReply", False),
        "author_username": author.get("userName"),
        "author_name": author.get("name"),
        "media": media,
        "has_video": any(m.get("type") == "video" for m in media),
        "quoted_tweet_id": quoted.get("id"),
        "quoted_author": (quoted.get("author") or {}).get("userName"),
        "retweeted_tweet_id": retweeted.get("id"),
        "retweeted_author": (retweeted.get("author") or {}).get("userName"),
    }


def _bucket_posts(posts: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {
        "originals": [],
        "quotes": [],
        "retweets": [],
        "replies": [],
    }
    for post in posts:
        key = {
            "original": "originals",
            "quote": "quotes",
            "retweet": "retweets",
            "reply": "replies",
        }.get(post["post_type"], "originals")
        buckets[key].append(post)
    for items in buckets.values():
        items.sort(key=lambda p: p.get("view_count", 0), reverse=True)
    return buckets


def parse_tweet_id(url_or_id: str) -> str | None:
    text = (url_or_id or "").strip()
    if text.isdigit():
        return text
    match = TWEET_ID_RE.search(text) or STATUS_ID_RE.search(text)
    return match.group(1) if match else None


def _connected_user() -> dict | None:
    return session.get("user")


def _store_user(
    *,
    user_id: str,
    username: str,
    name: str = "",
    profile_image_url: str = "",
    connect_method: str = "oauth",
) -> None:
    session["user"] = {
        "id": user_id,
        "username": username.lstrip("@").lower(),
        "name": name or username,
        "profile_image_url": profile_image_url,
        "connect_method": connect_method,
    }


# --- Official X OAuth -------------------------------------------------------
def _store_oauth_token(payload: dict) -> None:
    session["oauth_token"] = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "expires_at": time.time() + int(payload.get("expires_in", 0)),
    }


def _refresh_x_token(refresh_token: str) -> dict:
    auth = base64.b64encode(f"{X_CLIENT_ID}:{X_CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        X_TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth}",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": X_CLIENT_ID,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _x_access_token() -> str | None:
    tok = session.get("oauth_token")
    if not tok:
        return None
    if tok.get("expires_at") and time.time() > tok["expires_at"] - 60:
        if not tok.get("refresh_token") or not X_CLIENT_SECRET:
            session.pop("oauth_token", None)
            return None
        _store_oauth_token(_refresh_x_token(tok["refresh_token"]))
        tok = session["oauth_token"]
    return tok["access_token"]


def _fetch_x_me(access_token: str) -> dict:
    resp = requests.get(
        X_USER_ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"user.fields": "profile_image_url,name,username"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


# --- Routes -----------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/login")
def login():
    if not OAUTH_ENABLED:
        return redirect("/?dev=1")

    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    session["oauth_state"] = state
    session["code_verifier"] = verifier

    params = {
        "response_type": "code",
        "client_id": X_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{X_AUTH_URL}?{urlencode(params)}")


@app.route("/callback")
def callback():
    if request.args.get("error"):
        desc = request.args.get("error_description", request.args["error"])
        return f"Authorization failed: {desc}", 400
    if not request.args.get("code") or request.args.get("state") != session.get("oauth_state"):
        return "Invalid OAuth state or missing code.", 400

    body = {
        "grant_type": "authorization_code",
        "code": request.args["code"],
        "redirect_uri": REDIRECT_URI,
        "code_verifier": session.get("code_verifier", ""),
        "client_id": X_CLIENT_ID,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if X_CLIENT_SECRET:
        auth = base64.b64encode(f"{X_CLIENT_ID}:{X_CLIENT_SECRET}".encode()).decode()
        headers["Authorization"] = f"Basic {auth}"

    resp = requests.post(X_TOKEN_URL, headers=headers, data=body, timeout=15)
    payload = resp.json()
    if "access_token" not in payload:
        return f"Token exchange failed: {payload}", 400

    _store_oauth_token(payload)
    me = _fetch_x_me(payload["access_token"])
    _store_user(
        user_id=me.get("id", ""),
        username=me.get("username", ""),
        name=me.get("name", ""),
        profile_image_url=me.get("profile_image_url", ""),
        connect_method="oauth",
    )
    return redirect("/")


@app.route("/api/dev-connect", methods=["POST"])
def api_dev_connect():
    """Dev-only: bind an @handle without OAuth. Not for production."""
    if OAUTH_ENABLED:
        return jsonify({"error": "OAuth is configured — use /login instead."}), 400

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip().lstrip("@")
    if not username:
        return jsonify({"error": "username required"}), 400

    try:
        profile = _io_get("/twitter/user/info", {"userName": username})
    except requests.HTTPError as exc:
        return jsonify({"error": f"Could not resolve @{username}: {exc}"}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    user = profile.get("data") or {}
    if user.get("unavailable"):
        return jsonify({"error": user.get("message") or "Account unavailable"}), 400

    _store_user(
        user_id=user.get("id", username),
        username=user.get("userName") or username,
        name=user.get("name", ""),
        profile_image_url=user.get("profilePicture", ""),
        connect_method="dev_handle",
    )
    return jsonify({"ok": True, "user": session["user"]})


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/api/config")
def api_config():
    return jsonify({"oauth_enabled": OAUTH_ENABLED})


@app.route("/api/status")
def api_status():
    user = _connected_user()
    if not user:
        return jsonify({"connected": False, "oauth_enabled": OAUTH_ENABLED})

    # OAuth already gives us profile data — skip an extra twitterapi.io call here
    # to avoid burning rate limit before /api/posts runs.
    return jsonify({"connected": True, "oauth_enabled": OAUTH_ENABLED, "user": user})


@app.route("/api/posts")
def api_posts():
    user = _connected_user()
    if not user:
        return jsonify({"error": "not connected"}), 401

    cache_key = f"posts:v2:{user['username']}:{request.args.get('pages', '1')}"
    cached = session.get(cache_key)
    if cached and cached.get("expires_at", 0) > time.time():
        return jsonify(cached["payload"])

    posts: list[dict] = []
    cursor = ""
    pages = 0
    # One page (20 tweets) is enough for engine validation; pass ?pages=3 to fetch more.
    max_pages = min(int(request.args.get("pages", "1")), 3)

    while pages < max_pages:
        try:
            data = _io_get(
                "/twitter/user/last_tweets",
                {
                    "userName": user["username"],
                    "cursor": cursor,
                    "includeReplies": request.args.get("include_replies", "false").lower()
                    == "true",
                },
            )
        except IoRateLimited as exc:
            return jsonify({"error": str(exc), "retry_after": exc.retry_after}), 429
        except requests.HTTPError as exc:
            return jsonify({"error": f"twitterapi.io HTTP error: {exc}"}), 502
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        raw_tweets = _extract_tweets(data)
        posts.extend(_normalize_tweet(t) for t in raw_tweets)
        pages += 1
        if not data.get("has_next_page"):
            break
        cursor = data.get("next_cursor") or ""
        if not cursor:
            break

    buckets = _bucket_posts(posts)
    submittable = buckets["originals"] + buckets["quotes"]
    submittable.sort(key=lambda p: p.get("view_count", 0), reverse=True)
    total_views = sum(p.get("view_count", 0) for p in submittable)
    video_posts = [p for p in submittable if p.get("has_video")]

    payload = {
        "count": len(submittable),
        "video_count": len(video_posts),
        "total_views": total_views,
        "posts": submittable,
        "originals": buckets["originals"],
        "quotes": buckets["quotes"],
        "retweets": buckets["retweets"],
        "replies": buckets["replies"],
        "counts": {
            "fetched": len(posts),
            "original": len(buckets["originals"]),
            "quote": len(buckets["quotes"]),
            "retweet": len(buckets["retweets"]),
            "reply": len(buckets["replies"]),
            "submittable": len(submittable),
        },
        "username": user["username"],
    }
    if posts:
        session[cache_key] = {"expires_at": time.time() + 60, "payload": payload}
    return jsonify(payload)


@app.route("/api/verify")
def api_verify():
    """Engine simulation: verify a submission URL belongs to the connected user."""
    user = _connected_user()
    if not user:
        return jsonify({"error": "not connected"}), 401

    url = request.args.get("url", "").strip()
    tweet_id = parse_tweet_id(url)
    if not tweet_id:
        return jsonify({"error": "Could not parse tweet id from url"}), 400

    try:
        data = _io_get("/twitter/tweets", {"tweet_ids": tweet_id})
    except IoRateLimited as exc:
        return jsonify({"error": str(exc), "retry_after": exc.retry_after}), 429
    except requests.HTTPError as exc:
        return jsonify({"error": f"twitterapi.io HTTP error: {exc}"}), 502
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    tweets = _extract_tweets(data)
    if not tweets:
        return jsonify({"verified": False, "reason": "Tweet not found or not accessible"}), 404

    post = _normalize_tweet(tweets[0])
    author = (post.get("author_username") or "").lower()
    expected = user["username"].lower()
    owner_match = author == expected

    post_type = post.get("post_type", "original")
    content_eligible = post_type in {"original", "quote"}
    payout_eligible = owner_match and content_eligible and post.get("view_count", 0) > 0

    return jsonify(
        {
            "verified": owner_match and content_eligible,
            "owner_match": owner_match,
            "content_eligible": content_eligible,
            "post_type": post_type,
            "expected_username": expected,
            "author_username": author,
            "payout_eligible": payout_eligible,
            "reject_reason": None
            if content_eligible
            else f"Post type '{post_type}' is not eligible — only originals and quotes count.",
            "submission_url": url,
            "tweet_id": tweet_id,
            "metrics": {
                "views": post.get("view_count", 0),
                "likes": post.get("like_count", 0),
                "replies": post.get("reply_count", 0),
                "retweets": post.get("retweet_count", 0),
                "quotes": post.get("quote_count", 0),
            },
            "post": post,
        }
    )


@app.route("/api/replies")
def api_replies():
    """Fetch reply tweets for fraud/anomaly signals (author, text, engagement)."""
    tweet_id = parse_tweet_id(request.args.get("url", "") or request.args.get("tweet_id", ""))
    if not tweet_id:
        return jsonify({"error": "url or tweet_id required"}), 400

    replies: list[dict] = []
    cursor = ""
    max_pages = min(int(request.args.get("pages", "1")), 3)

    for _ in range(max_pages):
        try:
            data = _io_get(
                "/twitter/tweet/replies",
                {"tweetId": tweet_id, "cursor": cursor},
            )
        except IoRateLimited as exc:
            return jsonify({"error": str(exc), "retry_after": exc.retry_after}), 429
        except requests.HTTPError as exc:
            return jsonify({"error": f"twitterapi.io HTTP error: {exc}"}), 502
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        raw = _extract_tweets(data)
        replies.extend(_normalize_tweet(t) for t in raw)
        if not data.get("has_next_page"):
            break
        cursor = data.get("next_cursor") or ""
        if not cursor:
            break

    authors = {(r.get("author_username") or "").lower() for r in replies if r.get("author_username")}
    return jsonify(
        {
            "tweet_id": tweet_id,
            "count": len(replies),
            "unique_authors": len(authors),
            "replies": replies,
        }
    )


if __name__ == "__main__":
    mode = "OAuth + twitterapi.io" if OAUTH_ENABLED else "dev @handle + twitterapi.io"
    print(f" * Mode: {mode}")
    print(f" * Redirect URI (register in X developer portal): {REDIRECT_URI}")
    app.run(host="127.0.0.1", port=PORT, debug=True)
