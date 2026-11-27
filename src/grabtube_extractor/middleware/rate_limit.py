"""Per-IP, per-category rate limiting (FR-015).

In-memory sliding-window counters (consistent with the single-instance model). Job creation
and resolve are limited; status polling and downloads are not. Over-limit raises a
``ServiceError(rate_limited)`` carrying ``Retry-After``.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request

from ..models.domain import ErrorCode
from ..errors import ServiceError

WINDOW_S = 60.0


def client_ip(request: Request, trusted_header: str = "") -> str:
    """Rate-limit key. Never taken from client-settable headers such as X-Forwarded-For;
    only from ``trusted_header`` (one a trusted proxy overwrites) or the direct peer."""
    if trusted_header:
        value = request.headers.get(trusted_header, "").strip()
        if value:
            return value
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limits: dict[str, int], clock: Callable[[], float] = time.monotonic):
        self.limits = limits
        self.clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, ip: str, category: str) -> None:
        limit = self.limits.get(category)
        if not limit or limit <= 0:
            return
        now = self.clock()
        window_start = now - WINDOW_S
        bucket = self._hits[(ip, category)]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = int(WINDOW_S - (now - bucket[0])) + 1
            raise ServiceError(ErrorCode.rate_limited, retry_after=retry_after)
        bucket.append(now)


def make_dependency(category: str):
    """FastAPI dependency that enforces the limiter for ``category`` using app state."""

    async def _dep(request: Request) -> None:
        limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if limiter is not None:
            settings = getattr(request.app.state, "settings", None)
            header = settings.client_ip_header if settings is not None else ""
            limiter.check(client_ip(request, header), category)

    return _dep
