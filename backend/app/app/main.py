import traceback as tb

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import app
from app.api.api_v1.api import api_router as v1_router
from app.api.api_v2.api import api_router as v2_router
from app.core.config import settings


if settings.ROLLBAR_ENABLED:
    print("Initializing Rollbar")
    import rollbar

    rollbar.init(settings.ROLLBAR_KEY, environment=settings.ROLLBAR_ENV)


# https://github.com/tiangolo/fastapi/issues/775#issuecomment-592946834
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        tb.print_exc()
        if settings.ROLLBAR_ENABLED:
            if "JSONDecodeError" in str(e):
                rollbar.report_message(str(e), "warning")
            else:
                rollbar.report_exc_info()
        if settings.DEBUG:
            return Response(tb.format_exc(), status_code=500, media_type="text/plain")
        return Response(
            "Internal server error", status_code=500, media_type="text/plain"
        )


app.middleware("http")(catch_exceptions_middleware)


# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    print("Allowing origins: %s" % settings.BACKEND_CORS_ORIGINS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(v1_router, prefix=settings.API_V1_STR)
app.include_router(v2_router, prefix=settings.API_V2_STR)
