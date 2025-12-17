"""Async in-memory TTL cache.

Spec reference:
- PLANNING.md: Caching (cache.py)
- Issue: #16, Work-Item: PLAN-4.1
- Issue: #17, Work-Item: PLAN-4.2 (in-flight request deduplication)

Notes:
- In-memory only, async-safe via asyncio.Lock
- Deterministic eviction policy: FIFO by insertion order
- TTL calculations use a monotonic clock (time.monotonic)
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, MutableMapping, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")

NowFn = Callable[[], float]


@dataclass(frozen=True)
class _Entry(Generic[V]):
    value: V
    expires_at: float


class AsyncTTLCache(Generic[K, V]):
    """Async-safe in-memory TTL cache.

    - get/set/delete/clear are all async and protected by a single lock
    - Expiration uses a monotonic clock for robustness against system clock changes
    - Size is bounded by max_entries with FIFO eviction by insertion order
    """

    def __init__(
        self,
        *,
        default_ttl_seconds: int,
        max_entries: int,
        now_fn: NowFn | None = None,
    ) -> None:
        if default_ttl_seconds < 0:
            raise ValueError("default_ttl_seconds must be >= 0")
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")

        self._default_ttl = float(default_ttl_seconds)
        self._max_entries = int(max_entries)
        self._now: NowFn = now_fn or time.monotonic
        # Mapping of key -> (value, expires_at)
        self._data: MutableMapping[K, _Entry[V]] = {}
        # Maintain deterministic insertion order for FIFO eviction
        self._order: "OrderedDict[K, None]" = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: K) -> Optional[V]:
        async with self._lock:
            self._purge_expired_unlocked()
            entry = self._data.get(key)
            if entry is None:
                return None
            # Even after purge, double-check expiry (cheap and deterministic)
            if entry.expires_at <= self._now():
                # expire on access
                self._delete_unlocked(key)
                return None
            return entry.value

    async def set(self, key: K, value: V, ttl_seconds: Optional[int] = None) -> None:
        if ttl_seconds is not None and ttl_seconds < 0:
            raise ValueError("ttl_seconds must be >= 0 when provided")
        async with self._lock:
            self._purge_expired_unlocked()
            ttl = float(ttl_seconds) if ttl_seconds is not None else self._default_ttl
            expires_at = self._now() + ttl
            self._data[key] = _Entry(value=value, expires_at=expires_at)
            # Refresh insertion order: remove existing then append to end
            if key in self._order:
                del self._order[key]
            self._order[key] = None
            self._evict_if_needed_unlocked()

    async def delete(self, key: K) -> None:
        async with self._lock:
            self._delete_unlocked(key)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()
            self._order.clear()

    # --- internal helpers (require caller to hold lock) ---
    def _delete_unlocked(self, key: K) -> None:
        self._data.pop(key, None)
        if key in self._order:
            del self._order[key]

    def _purge_expired_unlocked(self) -> None:
        now = self._now()
        if not self._data:
            return
        # Iterate in insertion order for determinism while removing expired
        to_remove: list[K] = []
        for k in self._order.keys():
            entry = self._data.get(k)
            if entry is None:
                to_remove.append(k)
                continue
            if entry.expires_at <= now:
                to_remove.append(k)
        for k in to_remove:
            self._delete_unlocked(k)

    def _evict_if_needed_unlocked(self) -> None:
        # Evict in FIFO order until within bounds
        while len(self._data) > self._max_entries:
            # popitem(last=False) removes oldest
            try:
                oldest_key, _ = self._order.popitem(last=False)
            except KeyError:
                # nothing to evict
                break
            self._data.pop(oldest_key, None)


class InFlightDeduper(Generic[K, V]):
    """Deduplicate concurrent in-flight requests by key.

    Semantics (PLAN-4.2):
    - Only one underlying coroutine is created per key while it's running.
    - All awaiters await the same shared task; cancellation of a waiter does
      not cancel the underlying task (uses asyncio.shield).
    - On success or failure, the in-flight entry is removed.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._inflight: dict[K, asyncio.Task[V]] = {}

    async def run(self, key: K, coro_factory: Callable[[], Awaitable[V]]) -> V:
        """Run or join an in-flight task for ``key``.

        If a task for ``key`` is already running, this awaits it. Otherwise a
        new task is created from ``coro_factory`` and registered atomically.

        The shared task is awaited via ``asyncio.shield`` to prevent
        cancellation propagation from an individual waiter.
        """

        async with self._lock:
            task = self._inflight.get(key)
            if task is None or task.done():
                # Create and register a new task. Use a local wrapper so we can
                # ensure cleanup of the in-flight map regardless of outcome.
                async def _runner() -> V:
                    return await coro_factory()

                task = asyncio.create_task(_runner())

                def _cleanup(_t: asyncio.Task[V]) -> None:  # runs in loop thread
                    # Remove only if the current task is still the registered one
                    # to avoid races where a new task was installed for the same key.
                    if self._inflight.get(key) is _t:
                        self._inflight.pop(key, None)

                task.add_done_callback(_cleanup)
                self._inflight[key] = task

        # Await outside the lock to avoid blocking other keys.
        try:
            return await asyncio.shield(task)
        except Exception:
            # Exception is propagated to all awaiters; cleanup handled by callback.
            raise

    def has_inflight(self, key: K) -> bool:
        """Introspection for tests: whether a non-done task is tracked for key."""
        task = self._inflight.get(key)
        return bool(task is not None and not task.done())


__all__ = ["AsyncTTLCache", "InFlightDeduper"]
