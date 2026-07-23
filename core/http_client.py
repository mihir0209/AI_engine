"""HTTP client helpers — sync (requests) and async (httpx) backends.

Keeps provider code free of transport details. Prefer httpx when available;
fall back to requests for environments without httpx.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterator, Optional

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

import requests


def post_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Any = None,
    data: Any = None,
    timeout: float = 60,
) -> requests.Response:
    """Synchronous JSON POST via requests."""
    return requests.post(url, headers=headers, json=json_body, data=data, timeout=timeout)


def get_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60,
) -> requests.Response:
    """Synchronous GET via requests."""
    return requests.get(url, headers=headers, timeout=timeout)


def stream_sse(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Any = None,
    timeout: float = 60,
) -> Iterator[str]:
    """Yield SSE data lines (without the leading 'data: ') from a streaming POST."""
    with requests.post(url, headers=headers, json=json_body, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8", errors="replace")
            if decoded.startswith("data: "):
                yield decoded[6:]


async def apost_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Any = None,
    data: Any = None,
    timeout: float = 60,
) -> Dict[str, Any]:
    """Async JSON POST via httpx. Returns {status_code, json, text}."""
    if httpx is None:
        raise RuntimeError("httpx is required for async provider requests")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=json_body, content=data)
        try:
            body = resp.json()
        except Exception:
            body = None
        return {"status_code": resp.status_code, "json": body, "text": resp.text}


async def astream_sse(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Any = None,
    timeout: float = 60,
) -> AsyncIterator[str]:
    """Async SSE streaming via httpx. Yields data-line payloads."""
    if httpx is None:
        raise RuntimeError("httpx is required for async streaming")
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=headers, json=json_body) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                raise RuntimeError(f"HTTP {resp.status_code}: {text[:200]!r}")
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    yield line[6:]
