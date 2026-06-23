from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.settings import get_settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def enforce(self, *, bucket: str, key: str, limit: int, window_seconds: int = 60) -> None:
        now = monotonic()
        composite_key = f"{bucket}:{key}"
        with self._lock:
            window = self._events[composite_key]
            while window and now - window[0] >= window_seconds:
                window.popleft()

            if len(window) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please wait a minute and try again.",
                )

            window.append(now)


rate_limiter = InMemoryRateLimiter()


def rate_limit_auth_requests(request: Request) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    rate_limiter.enforce(
        bucket="auth",
        key=f"{client_host}:{request.url.path}",
        limit=settings.rate_limit_auth_per_minute,
    )
