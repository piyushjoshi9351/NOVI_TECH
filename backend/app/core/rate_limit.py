"""Thread-safe, per-process sliding windows for IP and account rate limits."""

import math
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._last_cleanup = 0.0

    def check(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            if now - self._last_cleanup >= self.window_seconds:
                self._hits = {
                    ip: hits for ip, hits in self._hits.items()
                    if hits and hits[-1] > cutoff
                }
                self._last_cleanup = now
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, math.ceil(hits[0] + self.window_seconds - now))
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._last_cleanup = 0.0


class IpRateLimiter(RateLimiter):
    def __call__(self, request: Request) -> None:
        # Trusted proxy middleware normalizes this address. Never trust raw
        # forwarding headers here: direct clients can supply arbitrary values.
        address = request.client.host if request.client else "unknown"
        self.check(address)


login_limiter = IpRateLimiter(limit=20)
signup_limiter = IpRateLimiter(limit=5)
