from fastapi import APIRouter

from app.api.routes import assistant, auth, compliance, dashboard, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(assistant.router)
api_router.include_router(compliance.router)
