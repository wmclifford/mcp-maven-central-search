import asyncio
from typing import Any

import httpx
import pytest
import respx

from mcp_maven_central_search.central_api import MavenCentralHttpClient


class NoSleep:
    async def __call__(self, *_: Any, **__: Any) -> None:  # no real delay
        return None


@pytest.mark.asyncio
async def test_successful_get_returns_json_respx() -> None:
    url = "https://example.com/data"
    payload = {"ok": True}
    client = MavenCentralHttpClient(sleep_fn=NoSleep())
    try:
        with respx.mock(assert_all_called=True) as router:
            router.get(url).mock(return_value=httpx.Response(200, json=payload))
            data = await client.get_json(url)
            assert data == payload
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_timeout_error_retries_then_succeeds() -> None:
    url = "https://example.com/retry"
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectTimeout("timeout")
        return httpx.Response(200, json={"attempt": calls["n"]})

    client = MavenCentralHttpClient(max_retries=4, sleep_fn=NoSleep())
    try:
        with respx.mock(assert_all_called=True) as router:
            router.get(url).mock(side_effect=handler)
            data = await client.get_json(url)
            assert data["attempt"] == 3
            assert calls["n"] == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_500_retries_then_fails_after_max() -> None:
    url = "https://example.com/err"
    client = MavenCentralHttpClient(max_retries=2, sleep_fn=NoSleep())
    try:
        with respx.mock(assert_all_called=True) as router:
            router.get(url).mock(return_value=httpx.Response(500, json={"error": "boom"}))
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_json(url)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_400_does_not_retry() -> None:
    url = "https://example.com/bad"
    client = MavenCentralHttpClient(max_retries=5, sleep_fn=NoSleep())
    try:
        with respx.mock(assert_all_called=True) as router:
            route = router.get(url).mock(return_value=httpx.Response(400, json={"bad": True}))
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_json(url)
            # ensure called only once
            assert route.call_count == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_concurrency_semaphore_limits_parallel_requests() -> None:
    url = "https://example.com/slow"
    max_conc = 2
    current = 0
    peak = 0

    async def slow_response(_: httpx.Request) -> httpx.Response:
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        # emulate some work but tiny delay
        await asyncio.sleep(0)
        current -= 1
        return httpx.Response(200, json={"ok": True})

    client = MavenCentralHttpClient(concurrency=max_conc, sleep_fn=NoSleep())
    try:
        with respx.mock(assert_all_called=True) as router:
            router.get(url).mock(side_effect=slow_response)
            # fire more tasks than concurrency
            tasks = [asyncio.create_task(client.get_json(url)) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            assert all(r["ok"] is True for r in results)
            assert peak <= max_conc
    finally:
        await client.aclose()
