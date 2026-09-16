"""A client for calling another module's `/internal/*` routes as if they
were a separate service — because the contract (X-Internal-Secret, JSON
over HTTP) is written as if they will be one someday.

Built on `httpx.ASGITransport`, which drives the *real* ASGI app in-process
— no socket, no port, but the actual routing, the actual dependency
(`require_internal_secret`), the actual response model. That's deliberately
more than a plain Python function call: it exercises the same contract
this module would have to honor if Intelligence (or anything else behind
`/internal/*`) were ever pulled out into its own deployable.
"""

from collections.abc import AsyncIterator

import httpx
from fastapi import Request

from .config import get_settings


async def get_internal_client(request: Request) -> AsyncIterator[httpx.AsyncClient]:
    settings = get_settings()
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://internal",
        headers={"X-Internal-Secret": settings.internal_service_secret},
        timeout=30.0,
    ) as client:
        yield client
