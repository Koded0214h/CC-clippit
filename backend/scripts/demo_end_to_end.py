"""Walk a real submission through the whole system and print what happens.

Brand signs up, creates a campaign, creator signs up, submits a link.
That submission crosses the module boundary into Intelligence, which
calls the platform for real, stores an observation, derives features and
judges trust. Then we read the numbers back the way earnings would.

    python scripts/demo_end_to_end.py --url "https://www.tiktok.com/@you/video/123..."

This exists because everything up to now has been proven against
recorded payloads and an in-memory database. None of that tells you
whether the pieces fit together against a live platform and real
Postgres — which is the only question this script asks.

Add --skip-connect if the creator account has already linked TikTok.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid

import httpx

API = os.environ.get("CLIPPIT_API", "http://localhost:8000")


def show(title: str, body) -> None:
    print(f"\n{'─' * 70}\n{title}\n{'─' * 70}")
    print(json.dumps(body, indent=2, default=str) if not isinstance(body, str) else body)


async def signup(client: httpx.AsyncClient, role: str) -> tuple[str, str]:
    """Fresh users each run so the script is re-runnable without cleanup.

    `example.com` rather than a `.test` domain: the email validator
    rejects reserved TLDs outright.
    """
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    password = "DemoPassword123!"
    r = await client.post(
        "/auth/signup",
        json={"email": email, "password": password, "full_name": f"Demo {role}", "role": role},
    )
    r.raise_for_status()
    r = await client.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    return email, token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="A real TikTok post URL owned by the connected account")
    parser.add_argument("--platform", default="tiktok")
    parser.add_argument("--skip-connect", action="store_true")
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=API, timeout=60.0) as client:
        # 1. A brand with a campaign to submit against. The role is
        #    called `organisation` in auth, not `brand`.
        _, brand_token = await signup(client, "organisation")
        r = await client.post(
            "/campaigns",
            headers=auth(brand_token),
            json={
                "title": "Demo campaign",
                "description": "End-to-end verification run.",
                "expected_views": 100_000,
                "platforms": [args.platform],
                "payout_rule": {
                    "rate_per_1000_views": 2.5,
                    "cap_amount": 500,
                    "min_views_threshold": 0,
                },
            },
        )
        if r.status_code >= 400:
            show("Campaign creation failed", r.text)
            return 1
        campaign = r.json()
        campaign_id = campaign["id"]
        await client.post(f"/campaigns/{campaign_id}/activate", headers=auth(brand_token))
        show("1. Campaign created and activated", {"id": campaign_id})

        # 2. A creator who has linked the platform account that owns the post.
        creator_email, creator_token = await signup(client, "creator")
        if not args.skip_connect:
            print(f"\n{'═' * 70}")
            print("2. Connect the TikTok account that owns that post.")
            print(f"{'═' * 70}")
            print("   Open this URL in your browser and complete the TikTok login:\n")
            print(f"   {API}/social/{args.platform}/login")
            print(f"\n   Log in as the creator first: {creator_email} / DemoPassword123!")
            print("   The Display API only ever returns the authorized account's own")
            print("   posts, so this has to be the account that published the URL.\n")
            input("   Press Enter once the account is connected... ")

        accounts = await client.get("/social/accounts", headers=auth(creator_token))
        show("2. Linked social accounts", accounts.json())

        # 3. The handoff. Koded's module writes the submission, then calls
        #    Intelligence, which is where the live platform call happens.
        r = await client.post(
            "/submissions",
            headers=auth(creator_token),
            json={"campaign_id": campaign_id, "platform": args.platform, "url": args.url},
        )
        if r.status_code >= 400:
            show(f"3. Submission rejected ({r.status_code})", r.text)
            print("\nA 4xx here is usually the platform refusing the call — an expired")
            print("token, or a post the connected account doesn't own. The typed error")
            print("in the body says which.")
            return 1
        submission = r.json()
        show("3. Submitted — Intelligence called the platform live", submission)
        submission_id = submission["id"]

        # 4. The read path earnings uses. No platform call here by design:
        #    nobody's payout should wait on TikTok's uptime.
        perf = await client.get(
            f"/submissions/{submission_id}/performance", headers=auth(creator_token)
        )
        show("4. Performance (what earnings bills from)", perf.json())

        # 5. The trust verdict. One observation in, so this should say
        #    insufficient_data rather than pretending to know.
        secret = os.environ.get("INTERNAL_SERVICE_SECRET", "")
        trust = await client.get(
            f"/internal/submissions/{submission_id}/trust",
            headers={"X-Internal-Secret": secret},
        )
        show("5. Trust verdict", trust.json() if trust.status_code < 400 else trust.text)

        print(f"\n{'═' * 70}")
        print("Done. To watch a time series actually grow, run the poller:")
        print("    python -m modules.intelligence.worker")
        print("Each pass appends a snapshot, recomputes features, re-judges trust.")
        print(f"{'═' * 70}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
