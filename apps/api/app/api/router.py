from fastapi import APIRouter

from app.api.routes import (
    assistant,
    auth,
    compliance,
    dashboard,
    health,
    hsn,
    incentives,
    rates,
    shipments,
    tools,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(assistant.router)
api_router.include_router(shipments.router)
api_router.include_router(compliance.router)
api_router.include_router(hsn.router)
api_router.include_router(incentives.router)
api_router.include_router(rates.router)
api_router.include_router(tools.router)
