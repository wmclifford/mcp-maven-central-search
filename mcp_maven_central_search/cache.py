"""Async in-memory TTL cache.

Spec reference:
- PLANNING.md: Caching (cache.py)
- Issue: #16, Work-Item: PLAN-4.1

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
from typing import Callable, Generic, MutableMapping, Optional, TypeVar

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


__all__ = ["AsyncTTLCache"]
