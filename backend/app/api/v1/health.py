from fastapi import APIRouter

from ...core.config import get_settings
from ...core.db import database_status

router = APIRouter()
settings = get_settings()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready")
def ready() -> dict:
    db = database_status()
    return {
        "status": "ok" if db["status"] == "ok" else "unavailable",
        "app": settings.app_name,
        "version": settings.app_version,
        "checks": {"database": db},
    }
