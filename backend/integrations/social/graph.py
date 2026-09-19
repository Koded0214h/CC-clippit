"""Shared HTTP error mapping for Graph-style adapters (Instagram, Facebook, Threads)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import CreatorTokenExpired, RateLimited, UpstreamError


def raise_for_graph(resp: httpx.Response, *, platform: str) -> dict[str, Any]:
    """Map Graph HTTP + `{error: {...}}` bodies onto typed adapter errors."""
    if resp.status_code == 429:
        retry = resp.headers.get("Retry-After")
        raise RateLimited(
            f"{platform} rate limit hit.",
            retry_after=int(retry) if retry and str(retry).isdigit() else None,
        )
    if resp.status_code in (401, 403):
        raise CreatorTokenExpired(
            f"{platform} rejected the creator's access token (HTTP {resp.status_code})."
        )
    try:
        payload = resp.json()
    except ValueError as exc:
        if resp.status_code >= 500:
            raise UpstreamError(f"{platform} returned HTTP {resp.status_code}.") from exc
        raise UpstreamError(f"{platform} returned a non-JSON body.") from exc

    error = payload.get("error") if isinstance(payload, dict) else None
    if error:
        code = error.get("code")
        message = error.get("message") or "no message"
        detail = f"{platform} error {code}: {message}"
        if code in (190, 102, 463, 467) or resp.status_code in (401, 403):
            raise CreatorTokenExpired(detail)
        if code == 4 or resp.status_code == 429:
            raise RateLimited(detail)
        if resp.status_code >= 500 or code in (1, 2):
            raise UpstreamError(detail)
        raise UpstreamError(detail)

    if resp.status_code >= 500:
        raise UpstreamError(f"{platform} returned HTTP {resp.status_code}.")
    if resp.status_code >= 400:
        raise UpstreamError(f"{platform} returned HTTP {resp.status_code}.")
    return payload if isinstance(payload, dict) else {}
