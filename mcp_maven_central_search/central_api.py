"""HTTP client wrapper for Maven Central interactions.

Implements PLAN-1.2 (Issue #7):
- Shared httpx.AsyncClient with connection pooling
- Timeouts, bounded retries with backoff, bounded concurrency via semaphore
- HTTPS-only guard on base URLs
- Minimal API to fetch JSON responses

Notes:
- Logs use the centralized logger and therefore go to stderr only.
- Caching is out of scope here; this module is transport-neutral.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from .config import Settings

_logger = logging.getLogger(__name__)


class MavenCentralHttpClient:
    """Resilient async HTTP client for Maven Central API.

    Parameters are sourced from Settings by default, but can be overridden
    for testability.
    """

    def __init__(
            self,
            *,
            base_url: str | None = None,
            timeout_seconds: Optional[int] = None,
            max_retries: Optional[int] = None,
            concurrency: Optional[int] = None,
            client: httpx.AsyncClient | None = None,
            sleep_fn: Any | None = None,
    ) -> None:
        s = Settings()
        self._base_url = base_url or s.MAVEN_CENTRAL_BASE_URL
        self._remote_content_base_url = s.MAVEN_CENTRAL_REMOTE_CONTENT_BASE_URL

        if not self._base_url.lower().startswith("https://"):
            raise ValueError("Base URL must be HTTPS")

        self._timeout_seconds = int(timeout_seconds or s.HTTP_TIMEOUT_SECONDS)
        self._max_retries = int(max_retries if max_retries is not None else s.HTTP_MAX_RETRIES)

        conc = int(concurrency or s.HTTP_CONCURRENCY)
        if conc < 1:
            raise ValueError("HTTP_CONCURRENCY must be >= 1")
        self._sem = asyncio.Semaphore(conc)

        self._client = client or httpx.AsyncClient(timeout=self._timeout_seconds)
        # Injected sleep function for tests to avoid real delays
        self._sleep = sleep_fn or asyncio.sleep

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- Retry policy helpers ---
    def _should_retry(self, exc: BaseException | None, response: httpx.Response | None) -> bool:
        if exc is not None:
            # Network-level transient errors and timeouts
            if isinstance(
                    exc,
                    (
                            httpx.ConnectError,
                            httpx.ReadTimeout,
                            httpx.WriteError,
                            httpx.RemoteProtocolError,
                            httpx.ConnectTimeout,
                            httpx.NetworkError,
                    ),
            ):
                return True
            return False
        if response is None:
            return False
        # Retry on 429 and 5xx
        status = response.status_code
        if status == 429 or 500 <= status <= 599:
            return True
        return False

    async def _backoff(self, attempt: int) -> None:
        # simple exponential backoff: 0.05, 0.1, 0.2, ... seconds
        delay = 0.05 * (2 ** max(0, attempt - 1))
        await self._sleep(delay)

    async def get_json(self, url: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """GET the provided URL and parse JSON with retries.

        The URL must be HTTPS. Only transient failures are retried.
        """
        if not url.lower().startswith("https://"):
            raise ValueError("URL must be HTTPS")

        # Note: guard against leaking sensitive params in logs (none expected now)
        _logger.debug("HTTP GET JSON", extra={"op": "get_json"})

        last_exc: BaseException | None = None
        last_response: httpx.Response | None = None

        for attempt in range(0, self._max_retries + 1):
            exc: BaseException | None = None
            resp: httpx.Response | None = None
            async with self._sem:
                try:
                    resp = await self._client.get(url, params=params)
                    if not self._should_retry(None, resp):
                        resp.raise_for_status()
                        return resp.json()
                except httpx.HTTPStatusError as e:
                    # Non-retriable statuses are surfaced immediately
                    if not self._should_retry(None, e.response):
                        raise
                    exc = e
                except Exception as e:  # network errors
                    exc = e

            last_exc = exc
            last_response = resp
            if attempt < self._max_retries and self._should_retry(exc, resp):
                await self._backoff(attempt + 1)
                continue
            break

        # Exhausted retries
        if last_exc is not None:
            raise last_exc
        if last_response is not None:
            last_response.raise_for_status()
        # Fallback - should not hit in normal flow
        raise RuntimeError("Request failed without response or exception")


# Simple module-level singleton for convenience
_singleton: MavenCentralHttpClient | None = None


def get_client() -> MavenCentralHttpClient:
    global _singleton
    if _singleton is None:
        _singleton = MavenCentralHttpClient()
    return _singleton


async def close_client() -> None:
    global _singleton
    if _singleton is not None:
        await _singleton.aclose()
        _singleton = None


__all__ = [
    "MavenCentralHttpClient",
    "get_client",
    "close_client",
]
