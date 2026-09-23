import os, json, secrets, hashlib, base64
from flask import Flask, redirect, request, session, jsonify
import requests
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

load_dotenv()


def pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(16))

CLIENT_ID     = os.environ["TWITTER_CLIENT_ID"]
CLIENT_SECRET = os.environ["TWITTER_CLIENT_SECRET"]
REDIRECT_URI  = "http://localhost:8000/callback"

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
    verifier, challenge = pkce_pair()
    session["code_verifier"] = verifier
    oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPES)
    url, state = oauth.authorization_url(
        AUTH_URL,
        code_challenge=challenge,
        code_challenge_method="S256",
    )
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
        code_verifier=session.get("code_verifier"),
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
    app.run(debug=True, port=8000)