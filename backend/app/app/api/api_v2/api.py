from fastapi import APIRouter

from app.api.api_v2.endpoints import zar

api_router = APIRouter()
api_router.include_router(zar.router, tags=["zar/v2"])
