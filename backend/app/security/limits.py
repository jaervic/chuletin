"""Limites de uso: concurrencia de ingesta y rate limiting en memoria."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict


class RateLimiter:
    """Token bucket sencillo por clave (IP, accion)."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill)
            if tokens < 1.0:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1.0, now)
            if len(self._buckets) > 5000:
                self._buckets = {k: v for k, v in self._buckets.items() if now - v[1] < 3600}
            return True


chat_limiter = RateLimiter(capacity=12, refill_per_second=0.4)     # ~24/min
ingest_limiter = RateLimiter(capacity=6, refill_per_second=0.1)    # ~6/min
write_limiter = RateLimiter(capacity=30, refill_per_second=1.0)    # ~90/min

_ingest_semaphore: asyncio.Semaphore | None = None
_study_semaphore: asyncio.Semaphore | None = None
_semaphore_lock = threading.Lock()


def ingest_semaphore() -> asyncio.Semaphore:
    """Solo una indexacion a la vez: protege la RAM y el disco."""
    global _ingest_semaphore
    with _semaphore_lock:
        if _ingest_semaphore is None:
            _ingest_semaphore = asyncio.Semaphore(1)
        return _ingest_semaphore


def study_semaphore() -> asyncio.Semaphore:
    """Solo una generacion de estudio a la vez."""
    global _study_semaphore
    with _semaphore_lock:
        if _study_semaphore is None:
            _study_semaphore = asyncio.Semaphore(1)
        return _study_semaphore


def client_key(request) -> str:
    client = getattr(request, "client", None)
    return getattr(client, "host", "desconocido") or "desconocido"


class Counter:
    """Contador simple para metricas internas."""

    def __init__(self) -> None:
        self._values: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def incr(self, key: str) -> None:
        with self._lock:
            self._values[key] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)
