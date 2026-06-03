from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn.protocols.utils

from app.core.config import settings
from app.core.logging import default_logger, dbg, info, warn, error
from app.db.session import database
from app.geo import close_maxmind_geoip, init_criteria_area_codes, init_maxmind_geoip
from app.utils import extract_header_params


def get_client_from_scope(scope):
    """HACK: extract client IP from uvicorn scope dict"""
    client = scope.get("client")
    if not client:
        return ""
    return client[0]  # ('127.0.0.1', 8080)


def get_real_client_addr(scope):
    """HACK: override for uvicorn's get_client_addr"""
    headers = {
        "".join(map(chr, k)): "".join(map(chr, v)) for k, v in scope.get("headers", [])
    }
    params = extract_header_params(headers)
    return params["ip"] or get_client_from_scope(scope)


# NOTE: this only works when running in production mode with
# gunicorn. In dev mode it launches uvicorn standalone and
# this code has no effect.
uvicorn.protocols.utils.get_client_addr = get_real_client_addr


@asynccontextmanager
async def lifespan(app):
    await database.connect()
    if settings.CRITERIA_AREA_CODES_PATH:
        init_criteria_area_codes()
    if settings.MAXMIND_GEOIP_ACCOUNT_ID and settings.MAXMIND_GEOIP_LICENSE_KEY:
        init_maxmind_geoip()

    print("FastAPI app started with async database connection")
    try:
        yield  # Hand control to the app
    finally:
        close_maxmind_geoip()
        await database.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENABLE_DOCS else None,
    docs_url=None,  # Swagger docs
    redoc_url="/docs" if settings.ENABLE_DOCS else None,  # redocs
    lifespan=lifespan,
)
