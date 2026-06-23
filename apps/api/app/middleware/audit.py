from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token
from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.services.audit import AuditLogger


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        settings = get_settings()
        if not settings.audit_logging_enabled or not request.url.path.startswith(
            settings.api_v1_prefix,
        ):
            return response

        actor_user_id = None
        tenant_id = None
        authorization = request.headers.get("Authorization")
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.removeprefix("Bearer ").removeprefix("bearer ").strip()
            try:
                payload = decode_access_token(token)
                actor_user_id = payload.sub
                tenant_id = payload.tenant_id
            except Exception:  # noqa: BLE001
                actor_user_id = None
                tenant_id = None

        session = SessionLocal()
        try:
            AuditLogger(session).log(
                action="http.request",
                entity_type="request",
                entity_id=request.url.path,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                route=request.url.path,
                method=request.method,
                details={"status_code": response.status_code},
            )
            session.commit()
        finally:
            session.close()

        return response