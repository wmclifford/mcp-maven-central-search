import pytest

from mcp_maven_central_search.cache import AsyncTTLCache


class TestClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def now(self) -> float:  # acts as NowFn
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt


@pytest.mark.asyncio
async def test_set_get_before_expiry() -> None:
    clock = TestClock()
    cache: AsyncTTLCache[str, int] = AsyncTTLCache(
        default_ttl_seconds=10,
        max_entries=10,
        now_fn=clock.now,
    )

    await cache.set("a", 1)
    assert await cache.get("a") == 1


@pytest.mark.asyncio
async def test_not_returned_after_expiry() -> None:
    clock = TestClock()
    cache: AsyncTTLCache[str, int] = AsyncTTLCache(
        default_ttl_seconds=5,
        max_entries=10,
        now_fn=clock.now,
    )

    await cache.set("a", 1)
    # Advance just past TTL
    clock.advance(5.0001)
    assert await cache.get("a") is None


@pytest.mark.asyncio
async def test_eviction_when_max_entries_exceeded_fifo() -> None:
    clock = TestClock()
    cache: AsyncTTLCache[str, int] = AsyncTTLCache(
        default_ttl_seconds=100,
        max_entries=2,
        now_fn=clock.now,
    )

    await cache.set("k1", 1)
    await cache.set("k2", 2)
    # Exceed capacity -> evict oldest (k1)
    await cache.set("k3", 3)

    assert await cache.get("k1") is None
    assert await cache.get("k2") == 2
    assert await cache.get("k3") == 3


@pytest.mark.asyncio
async def test_delete_removes_item() -> None:
    clock = TestClock()
    cache: AsyncTTLCache[str, int] = AsyncTTLCache(
        default_ttl_seconds=10,
        max_entries=10,
        now_fn=clock.now,
    )

    await cache.set("a", 1)
    await cache.delete("a")
    assert await cache.get("a") is None


@pytest.mark.asyncio
async def test_clear_removes_all_items() -> None:
    clock = TestClock()
    cache: AsyncTTLCache[str, int] = AsyncTTLCache(
        default_ttl_seconds=10,
        max_entries=10,
        now_fn=clock.now,
    )

    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None
