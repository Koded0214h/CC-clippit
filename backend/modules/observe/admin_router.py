"""Ops feeds for the admin app's "System health" and "Trust & delivery" screens.

REST for a first paint and a WebSocket (`/admin/ws`) to keep the screens live.
Both serve the same payloads (see `ops.py` and architecture/ops-api.md), and
both sit behind the normal operator login.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.admin.router import require_admin
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User

from . import collector, ops

logger = logging.getLogger("clippit.observe")
router = APIRouter(prefix="/admin", tags=["admin"])

SNAPSHOT_SECONDS = 10
AUTH_TIMEOUT_SECONDS = 5


@router.get("/system/health")
async def system_health(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await ops.system(db)


@router.get("/delivery/webhooks")
async def webhook_delivery(admin: User = Depends(require_admin)):
    return ops.webhooks()


@router.get("/delivery/social")
async def social_delivery(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await ops.social(db)


@router.get("/delivery/notifications")
async def notification_delivery(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await ops.notifications(db)


@router.get("/ops/snapshot")
async def snapshot(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """All four topics in one call (what the WebSocket pushes, without the socket)."""
    return {topic: await ops.build(topic, db) for topic in ops.TOPICS}


# --- WebSocket ------------------------------------------------------------------------
#
# Browsers cannot set an Authorization header on a WebSocket, and a token in the URL
# would land in access logs. So: connect, then send {"type":"auth","token":"<access token>"}
# as the first message (within 5 s). The server answers {"type":"ready", "topics":[...]}.

def _session(app):
    """A short-lived DB session honouring dependency overrides (tests)."""
    return asynccontextmanager(app.dependency_overrides.get(get_db, get_db))()


async def _authenticate(ws: WebSocket) -> User | None:
    try:
        first = await asyncio.wait_for(ws.receive_json(), AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
        await ws.close(code=4401, reason="Send an auth message first")
        return None
    if not isinstance(first, dict) or first.get("type") != "auth" or not isinstance(first.get("token"), str):
        await ws.close(code=4401, reason="Send an auth message first")
        return None
    try:
        async with _session(ws.app) as db:
            user = await get_current_user(first["token"], db)
    except HTTPException:
        await ws.close(code=4401, reason="Not authenticated")
        return None
    if user.role != Role.admin:
        await ws.close(code=4403, reason="Admin only")
        return None
    return user


@router.websocket("/ws")
async def ops_socket(ws: WebSocket):
    await ws.accept()
    if await _authenticate(ws) is None:
        return

    topics = set(ops.TOPICS)
    kick = asyncio.Event()
    send_lock = asyncio.Lock()
    queue = collector.subscribe()

    async def send(payload: dict) -> None:
        async with send_lock:
            await ws.send_json(payload)

    await send({"type": "ready", "topics": sorted(topics), "snapshot_seconds": SNAPSHOT_SECONDS})

    async def snapshots() -> None:
        while True:
            for topic in sorted(topics):
                # The session lives only while building: never held across a send or a wait.
                try:
                    async with _session(ws.app) as db:
                        payload = {"type": "snapshot", "topic": topic, "data": await ops.build(topic, db)}
                except Exception:  # noqa: BLE001 — one bad topic must not kill the stream
                    logger.warning("ops snapshot %s failed", topic, exc_info=True)
                    payload = {"type": "error", "topic": topic, "message": "could not build this topic"}
                await send(payload)
            kick.clear()
            try:
                await asyncio.wait_for(kick.wait(), SNAPSHOT_SECONDS)
            except asyncio.TimeoutError:
                pass

    async def events() -> None:
        while True:
            message = await queue.get()
            if message["topic"] in topics:
                await send(message)

    async def reader() -> None:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "ping":
                await send({"type": "pong"})
            elif kind == "subscribe" and isinstance(msg.get("topics"), list):
                chosen = {t for t in msg["topics"] if t in ops.TOPICS}
                topics.clear()
                topics.update(chosen)
                await send({"type": "subscribed", "topics": sorted(topics)})
                kick.set()  # push fresh snapshots for the new selection now

    tasks = [asyncio.create_task(fn()) for fn in (snapshots, events, reader)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                logger.warning("ops socket ended: %s: %s", type(exc).__name__, exc)
    finally:
        collector.unsubscribe(queue)
        for task in tasks:
            task.cancel()
        await asyncio.wait(tasks, timeout=2)  # bounded: cleanup must never hang the connection
