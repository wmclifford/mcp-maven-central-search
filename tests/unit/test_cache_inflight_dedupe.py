import asyncio
from typing import Any

import pytest

from mcp_maven_central_search.cache import InFlightDeduper


@pytest.mark.asyncio
async def test_dedup_success_single_underlying_call() -> None:
    deduper: InFlightDeduper[str, int] = InFlightDeduper()

    started = asyncio.Event()
    proceed = asyncio.Event()
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        started.set()
        await proceed.wait()
        return 42

    async def waiter() -> int:
        return await deduper.run("key", factory)

    # Launch multiple concurrent waiters
    tasks = [asyncio.create_task(waiter()) for _ in range(5)]

    # Wait until the underlying factory actually started
    await started.wait()
    # Allow completion
    proceed.set()

    results = await asyncio.gather(*tasks)
    assert results == [42, 42, 42, 42, 42]
    assert calls == 1
    # Cleanup should have removed the in-flight entry
    assert not deduper.has_inflight("key")


@pytest.mark.asyncio
async def test_dedup_failure_propagates_and_clears() -> None:
    deduper: InFlightDeduper[str, int] = InFlightDeduper()

    proceed = asyncio.Event()
    calls = 0

    class Boom(RuntimeError):
        pass

    async def factory() -> int:
        nonlocal calls
        calls += 1
        await proceed.wait()
        raise Boom("boom")

    async def waiter() -> Any:
        return await deduper.run("key", factory)

    t1 = asyncio.create_task(waiter())
    t2 = asyncio.create_task(waiter())
    proceed.set()

    for t in (t1, t2):
        with pytest.raises(Boom):
            await t

    # Underlying called only once
    assert calls == 1
    # Cleanup: no in-flight entry remains
    assert not deduper.has_inflight("key")

    # Subsequent invocation should trigger a new call
    proceed2 = asyncio.Event()

    async def factory2() -> int:
        nonlocal calls
        calls += 1
        await proceed2.wait()
        return 7

    w = asyncio.create_task(deduper.run("key", factory2))
    proceed2.set()
    assert await w == 7
    assert calls == 2


@pytest.mark.asyncio
async def test_cancellation_of_one_waiter_does_not_cancel_underlying() -> None:
    deduper: InFlightDeduper[str, int] = InFlightDeduper()

    proceed = asyncio.Event()
    started = asyncio.Event()
    factory_cancelled = False

    async def factory() -> str:
        nonlocal factory_cancelled
        started.set()
        try:
            await proceed.wait()
        except asyncio.CancelledError:
            factory_cancelled = True
            raise
        return "ok"

    w1 = asyncio.create_task(deduper.run("k", factory))
    w2 = asyncio.create_task(deduper.run("k", factory))

    await started.wait()

    # Cancel one waiter
    w1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await w1

    # Let the underlying complete
    proceed.set()

    # The other waiter should still complete successfully
    assert await w2 == "ok"
    # The underlying coroutine should not have been cancelled
    assert factory_cancelled is False
    # Cleanup
    assert not deduper.has_inflight("k")


@pytest.mark.asyncio
async def test_cleanup_after_success_or_failure() -> None:
    deduper: InFlightDeduper[str, int] = InFlightDeduper()

    # Success path
    assert await deduper.run("x", lambda: asyncio.sleep(0, result=1)) == 1
    assert not deduper.has_inflight("x")

    # Failure path
    async def bad() -> int:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await deduper.run("y", bad)
    assert not deduper.has_inflight("y")
