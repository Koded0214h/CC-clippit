"""The admin WebSocket: first-message auth, snapshots, subscribe, ping."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from modules.auth.models import Role
from modules.observe import admin_router, ops


class _User:
    def __init__(self, role):
        self.role = role


@pytest.fixture
def client(monkeypatch):
    async def fake_user(token, db):
        if token == "admin-token":
            return _User(Role.admin)
        if token == "creator-token":
            return _User(Role.creator)
        raise HTTPException(401)

    async def fake_build(topic, db):
        return {"topic": topic}

    monkeypatch.setattr(admin_router, "get_current_user", fake_user)
    monkeypatch.setattr(ops, "build", fake_build)
    app = FastAPI()
    app.include_router(admin_router.router)
    return TestClient(app)


def _closed_with(ws):
    with pytest.raises(WebSocketDisconnect) as info:
        ws.receive_json()
    return info.value.code


def test_rejects_a_first_message_that_is_not_auth(client):
    with client.websocket_connect("/admin/ws") as ws:
        ws.send_json({"type": "subscribe", "topics": ["system"]})
        assert _closed_with(ws) == 4401


def test_rejects_a_bad_token(client):
    with client.websocket_connect("/admin/ws") as ws:
        ws.send_json({"type": "auth", "token": "nope"})
        assert _closed_with(ws) == 4401


def test_rejects_a_non_admin(client):
    with client.websocket_connect("/admin/ws") as ws:
        ws.send_json({"type": "auth", "token": "creator-token"})
        assert _closed_with(ws) == 4403


def test_admin_gets_ready_then_a_snapshot_per_topic(client):
    with client.websocket_connect("/admin/ws") as ws:
        ws.send_json({"type": "auth", "token": "admin-token"})
        ready = ws.receive_json()
        assert ready["type"] == "ready" and ready["topics"] == sorted(ops.TOPICS)
        got = {ws.receive_json()["topic"] for _ in ops.TOPICS}
        assert got == set(ops.TOPICS)


def test_subscribe_narrows_topics_and_ping_pongs(client):
    with client.websocket_connect("/admin/ws") as ws:
        ws.send_json({"type": "auth", "token": "admin-token"})
        ws.receive_json()
        for _ in ops.TOPICS:
            ws.receive_json()
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        ws.send_json({"type": "subscribe", "topics": ["webhooks", "bogus"]})
        assert ws.receive_json() == {"type": "subscribed", "topics": ["webhooks"]}
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["topic"] == "webhooks"
