from fastapi import APIRouter

from app.api.routes import conversations, inference, reports, system

api_router = APIRouter(prefix="/api")
api_router.include_router(conversations.router)
api_router.include_router(reports.router)
api_router.include_router(inference.router)
api_router.include_router(system.router)
