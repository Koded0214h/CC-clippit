"""Pure-ASGI request timer feeding the collector (no BaseHTTPMiddleware: that
buffers streaming responses and adds a task hop to every request).

For failed requests it also keeps what someone debugging would ask for: the
exception and traceback, the raw path, query parameter *names*, client and
user-agent, and the first bytes of a 5xx response body. Never the query
values, cookies, authorization header or request body."""

import time
from urllib.parse import parse_qsl

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import collector

# The dashboard polling itself would otherwise drown out the traffic it measures.
_IGNORED_PREFIXES = ("/observe",)
_SAFE_HEADERS = ("user-agent", "content-type", "content-length", "origin", "referer", "accept")
_BODY_EXCERPT = 1000


class ObserveMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(_IGNORED_PREFIXES):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500
        body = bytearray()
        exception: BaseException | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and status >= 500 and len(body) < _BODY_EXCERPT:
                body.extend(message.get("body", b"")[: _BODY_EXCERPT - len(body)])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except BaseException as exc:  # noqa: BLE001 — recorded, then re-raised untouched
            exception = exc
            raise
        finally:
            try:
                route = scope.get("route")
                # Route template (/campaigns/{id}) rather than the raw path in the
                # headline: keeps the log line tidy and cardinality bounded.
                path = getattr(route, "path", None) or scope["path"]
                client = scope["client"][0] if scope.get("client") else None
                detail = None
                if status >= 400 or exception is not None:
                    headers = {k.decode("latin-1"): v.decode("latin-1")[:300] for k, v in scope.get("headers", []) if k.decode("latin-1") in _SAFE_HEADERS}
                    query = scope.get("query_string", b"").decode("latin-1")
                    detail = {
                        "raw_path": scope["path"],
                        "query_params": sorted({k for k, _ in parse_qsl(query, keep_blank_values=True)}),
                        "headers": headers,
                        "response_excerpt": bytes(body).decode("utf-8", "replace") if body else None,
                    }
                    if exception is not None:
                        detail["exception"] = collector.describe_exception(exception)
                collector.record_request(scope["method"], path, status, (time.perf_counter() - started) * 1000, client, detail)
            except Exception:  # noqa: BLE001
                pass
