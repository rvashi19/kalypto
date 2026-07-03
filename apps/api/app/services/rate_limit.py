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

    def enforce(
        self,
        *,
        bucket: str,
        key: str,
        limit: int,
        window_seconds: int = 60,
        message: str | None = None,
    ) -> None:
        now = monotonic()
        composite_key = f"{bucket}:{key}"
        with self._lock:
            window = self._events[composite_key]
            while window and now - window[0] >= window_seconds:
                window.popleft()

            if len(window) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=message or "Rate limit exceeded. Please wait a minute and try again.",
                )

            window.append(now)


rate_limiter = InMemoryRateLimiter()


def _enforce_distributed(
    *,
    bucket: str,
    key: str,
    limit: int,
    window_seconds: int = 60,
    message: str | None = None,
) -> None:
    settings = get_settings()
    try:
        client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        redis_key = f"rate-limit:{bucket}:{key}"
        count = client.incr(redis_key)
        if count == 1:
            client.expire(redis_key, window_seconds)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=message or "Rate limit exceeded. Please wait a minute and try again.",
            )
    except RedisError:
        rate_limiter.enforce(
            bucket=bucket,
            key=key,
            limit=limit,
            window_seconds=window_seconds,
            message=message,
        )


def rate_limit_auth_requests(request: Request) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    _enforce_distributed(
        bucket="auth",
        key=f"{client_host}:{request.url.path}",
        limit=settings.rate_limit_auth_per_minute,
    )


def rate_limit_auth_identity(request: Request, email: str) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    normalized_email = email.strip().lower()
    window_minutes = max(1, settings.rate_limit_auth_window_seconds // 60)
    _enforce_distributed(
        bucket="auth-identity",
        key=f"{client_host}:{normalized_email}:{request.url.path}",
        limit=settings.rate_limit_auth_attempts_per_window,
        window_seconds=settings.rate_limit_auth_window_seconds,
        message=f"Too many auth attempts. Wait {window_minutes} minutes and try again.",
    )


def rate_limit_upload_requests(request: Request) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    _enforce_distributed(
        bucket="upload",
        key=client_host,
        limit=settings.rate_limit_uploads_per_minute,
    )
