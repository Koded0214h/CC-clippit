"""/observe: disabled without a password, gated by login, records traffic."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import get_settings
from modules.observe import collector
from modules.observe.middleware import ObserveMiddleware
from modules.observe.router import router


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "observe_username", "ops")
    monkeypatch.setattr(get_settings(), "observe_password", "hunter2")
    app = FastAPI()
    app.add_middleware(ObserveMiddleware)
    app.include_router(router)

    @app.get("/ping/{item}")
    def ping(item: str):
        return {"item": item}

    # slowapi's decorator needs the limiter wired to the app. It's the same
    # process-wide singleton every other test uses (core.rate_limit.limiter),
    # and tests/http_app.py's `api` fixture disables it globally for the rest
    # of the session the first time anything signs up or logs in — so it must
    # be explicitly re-enabled here, not just reset, or this suite passes in
    # isolation and fails the moment any other test runs before it.
    from core.rate_limit import limiter
    app.state.limiter = limiter
    limiter.enabled = True
    limiter.reset()
    # The log ring buffer is the same kind of process-wide global (installed
    # once via main.py's install_log_capture()) — clear it so an earlier,
    # unrelated test's request isn't still the most recent "http" log line.
    collector._logs.clear()
    return TestClient(app)


def _login(client, user="ops", pw="hunter2"):
    return client.post("/observe/api/login", json={"username": user, "password": pw})


def test_disabled_without_password(monkeypatch):
    monkeypatch.setattr(get_settings(), "observe_password", "")
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).get("/observe").status_code == 404


def test_api_requires_session(client):
    assert client.get("/observe/api/summary").status_code == 401
    assert client.get("/observe/api/logs").status_code == 401
    assert client.get("/observe/api/logs", cookies={"observe_session": "9999999999.bad"}).status_code == 401


def test_wrong_credentials_rejected(client):
    assert _login(client, pw="nope").status_code == 401
    assert _login(client, user="nope").status_code == 401


def test_login_then_logs_include_traffic_with_route_template(client):
    client.get("/ping/secret-id-123?token=abc")
    assert _login(client).status_code == 200
    rows = client.get("/observe/api/logs").json()["logs"]
    line = next(r for r in rows if r["source"] == "http")
    assert line["path"] == "/ping/{item}"
    assert "token" not in line["message"] and "secret-id" not in line["message"]
    assert line["status"] == 200


def test_dashboard_polling_is_not_counted(client):
    _login(client)
    before = collector.snapshot()["requests"]
    client.get("/observe/api/logs")
    assert collector.snapshot()["requests"] == before


def test_page_served(client):
    r = client.get("/observe")
    assert r.status_code == 200 and "Clippit Observe" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_logs_after_cursor(client):
    _login(client)
    client.get("/ping/a")
    latest = client.get("/observe/api/logs").json()["latest"]
    assert client.get(f"/observe/api/logs?after={latest}").json()["logs"] == []
    client.get("/ping/b")
    assert len(client.get(f"/observe/api/logs?after={latest}").json()["logs"]) == 1


def test_summary_shape(client):
    _login(client)
    client.get("/ping/a")
    d = client.get("/observe/api/summary").json()
    assert d["health"]["liveness"]["ok"] is True
    assert "database" in d["health"] and len(d["series"]) == 30
    assert d["requests"] >= 1


def test_login_is_rate_limited(client):
    codes = [_login(client, pw="nope").status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and 429 in codes[5:]
