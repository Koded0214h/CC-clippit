"""A scriptable stand-in for Intelligence's `/internal/*` API.

Core talks to Intelligence only through `core.internal_client`, over the
contract in architecture/intelligence-contracts.md. Faking that seam — not
Intelligence's internals — is what lets these tests drive views, trust flags
and failures from the outside and still exercise every line of core.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx


def _response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body)


class FakeIntelligence:
    def __init__(self) -> None:
        self.views: dict[str, int] = {}
        self.comments: dict[str, int] = {}
        self.shares: dict[str, int] = {}
        self.snapshot: dict[str, str] = {}
        self.platform: dict[str, str] = {}
        self.url: dict[str, str] = {}
        self.trust: dict[str, str] = {}
        self.registered: list[dict] = []
        self.stopped: list[str] = []
        self.trust_reviews: list[dict] = []
        #: Set to (status, detail) to make the next registrations fail.
        self.fail_register: tuple[int, dict] | None = None
        #: Set to make every read raise like an unreachable service.
        self.unreachable = False
        self.initial_views = 0

    # -- scripting ---------------------------------------------------------
    def set_views(self, submission_id, views: int) -> None:
        key = str(submission_id)
        self.views[key] = views
        self.snapshot[key] = str(uuid.uuid4())

    def set_performance(
        self,
        submission_id,
        *,
        views: int,
        comments: int = 0,
        shares: int = 0,
    ) -> None:
        key = str(submission_id)
        self.views[key] = views
        self.comments[key] = comments
        self.shares[key] = shares
        self.snapshot[key] = str(uuid.uuid4())

    # -- the client interface core uses -----------------------------------
    async def post(self, url: str, json: dict | None = None, **_) -> httpx.Response:
        if self.unreachable:
            raise httpx.ConnectError("intelligence is down")
        parts = url.strip("/").split("/")  # internal / submissions / {id} / metrics|tracking / [stop]
        submission_id = parts[2]
        if parts[3] == "metrics":
            if self.fail_register:
                status, detail = self.fail_register
                return _response(status, {"detail": detail})
            self.registered.append(json or {})
            self.platform[submission_id] = (json or {}).get("platform", "tiktok")
            self.url[submission_id] = (json or {}).get("url", "")
            self.set_views(submission_id, self.initial_views)
            return _response(201, self._performance(submission_id))
        if parts[3] == "tracking" and parts[4] == "stop":
            self.stopped.append(submission_id)
            return _response(200, {})
        if parts[3] == "trust" and parts[4] == "review":
            self.trust_reviews.append({"submission_id": submission_id, **(json or {})})
            return _response(201, {"review_id": str(uuid.uuid4()), "evaluation_id": None, **(json or {})})
        return _response(404, {"detail": "unhandled in fake"})

    async def get(self, url: str, params: dict | None = None, **_) -> httpx.Response:
        if self.unreachable:
            raise httpx.ConnectError("intelligence is down")
        parts = url.strip("/").split("/")
        if parts[1:3] == ["trust", "rules"]:
            return _response(200, {"version": "fake-1", "rules": [], "active_since": datetime.now(timezone.utc).isoformat()})
        submission_id, what = parts[2], parts[3]
        if submission_id not in self.views:
            return _response(404, {"detail": {"code": "no_observations", "message": "none"}})
        if what == "performance":
            return _response(200, self._performance(submission_id))
        if what == "trust":
            return _response(
                200,
                {
                    "submission_id": submission_id,
                    "status": self.trust.get(submission_id, "normal"),
                    "anomaly_score": 0.9 if self.trust.get(submission_id) == "flagged" else 0.1,
                    "signals": [],
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        return _response(404, {"detail": "unhandled in fake"})

    def _performance(self, submission_id: str) -> dict:
        platform = self.platform.get(submission_id, "tiktok")
        return {
            "submission_id": submission_id,
            "content": {
                "platform": platform,
                "platform_content_id": f"vid-{submission_id[:8]}",
                "url": self.url.get(submission_id) or f"https://example.com/{submission_id}",
            },
            "metrics": {
                "views": self.views[submission_id],
                "likes": 10,
                "comments": self.comments.get(submission_id, 2),
                "shares": self.shares.get(submission_id, 0),
            },
            "features": {"observation_count": 1},
            "provenance": {
                "platform": platform,
                "source": "fake.intelligence",
                "snapshot_id": self.snapshot[submission_id],
                "observed_at": datetime.now(timezone.utc).isoformat(),
            },
            "tracking": None,
        }
