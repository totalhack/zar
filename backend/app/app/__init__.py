from contextlib import asynccontextmanager
import typing

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import orjson
import uvicorn.protocols.utils

from app.core.config import settings
from app.core.logging import default_logger, dbg, info, warn, error
from app.db.session import database
from app.geo import init_criteria_area_codes
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


# https://github.com/tiangolo/fastapi/issues/459#issuecomment-536781105
class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: typing.Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)


@asynccontextmanager
async def lifespan(app):
    await database.connect()
    if settings.CRITERIA_AREA_CODES_PATH:
        init_criteria_area_codes()
    print("FastAPI app started with async database connection")
    try:
        yield  # Hand control to the app
    finally:
        await database.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENABLE_DOCS else None,
    docs_url=None,  # Swagger docs
    redoc_url="/docs" if settings.ENABLE_DOCS else None,  # redocs
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)
