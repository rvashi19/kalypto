from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status
from redis import Redis
from redis.exceptions import RedisError

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


def _enforce_distributed(*, bucket: str, key: str, limit: int) -> None:
    settings = get_settings()
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        redis_key = f"rate-limit:{bucket}:{key}"
        count = client.incr(redis_key)
        if count == 1:
            client.expire(redis_key, 60)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait a minute and try again.",
            )
    except RedisError:
        rate_limiter.enforce(bucket=bucket, key=key, limit=limit)


def rate_limit_auth_requests(request: Request) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    _enforce_distributed(
        bucket="auth",
        key=f"{client_host}:{request.url.path}",
        limit=settings.rate_limit_auth_per_minute,
    )


def rate_limit_upload_requests(request: Request) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    _enforce_distributed(
        bucket="upload",
        key=client_host,
        limit=settings.rate_limit_uploads_per_minute,
    )
