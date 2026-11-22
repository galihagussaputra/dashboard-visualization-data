from fastapi import APIRouter

from .auth import router as auth_router
from .catalog import router as catalog_router
from .health import router as health_router
from .ingestion import router as ingestion_router
from .statements import router as statements_router
from .trust import router as trust_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(catalog_router, tags=["catalog"])
api_router.include_router(statements_router, tags=["statements"])
api_router.include_router(ingestion_router, tags=["ingestion"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(trust_router, tags=["trust"])
