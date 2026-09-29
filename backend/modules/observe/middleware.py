"""Pure-ASGI request timer feeding the collector (no BaseHTTPMiddleware: that
buffers streaming responses and adds a task hop to every request)."""

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import collector

# The dashboard polling itself would otherwise drown out the traffic it measures.
_IGNORED_PREFIXES = ("/observe",)


class ObserveMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(_IGNORED_PREFIXES):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            try:
                route = scope.get("route")
                # Route template (/campaigns/{id}) rather than the raw path:
                # keeps ids out of the log and the cardinality bounded. No query string, ever.
                path = getattr(route, "path", None) or scope["path"]
                client = scope["client"][0] if scope.get("client") else None
                collector.record_request(scope["method"], path, status, (time.perf_counter() - started) * 1000, client)
            except Exception:  # noqa: BLE001
                pass
