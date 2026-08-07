import warnings

warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.config.settings as settings
from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.history import router as history_router
from app.api.runtime import router as runtime_router
from app.api.youtube import router as youtube_router
from app.config.logger import Logger, log_event
from app.exceptions import AiLayerError
from app.i18n.responses import client_message, localize_detail
from app.lifecycle import shutdown, startup
from app.middleware.ip_address import GeoIPMiddleware
from app.middleware.locale import LocaleMiddleware
from app.middleware.rate_limit import RateLimitExceeded, limiter, rate_limit_exceeded_handler
from app.schemas.response import ApiResponse
from app.services.health import collect_checks, is_healthy

Logger.setup(level=settings.LOG_LEVEL)
logger = Logger.get(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan: load remote config and run startup tasks before serving,
    then run shutdown tasks when the app stops.

    Args:
        _app: The FastAPI application instance (unused)."""
    Logger.sync_uvicorn(settings.LOG_LEVEL)
    logger.info(log_event("startup", "loading remote config"))
    from app.config.remote import load_and_apply

    await load_and_apply()
    await startup()
    yield
    await shutdown()


app = FastAPI(
    title="AI Layer",
    description="AI-powered YouTube + TikTok analysis",
    version="1.0.0",
    debug=False,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LocaleMiddleware)
app.add_middleware(GeoIPMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.exception_handler(AiLayerError)
async def ai_layer_error_handler(request: Request, exc: AiLayerError) -> JSONResponse:
    """Convert an AiLayerError into a localized JSON error response.

    Args:
        request: Incoming request, used to resolve the client's locale.
        exc: The raised application error.

    Returns:
        JSONResponse with the error's HTTP status and a localized message."""
    from app.i18n.locale import resolve_locale

    locale = resolve_locale(request)
    return JSONResponse(
        status_code=exc.http_status,
        content=ApiResponse.fail(client_message(exc, locale)).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert a FastAPI HTTPException into a localized JSON error response.

    Args:
        request: Incoming request, used to resolve the client's locale.
        exc: The raised HTTP exception.

    Returns:
        JSONResponse with the exception's status code and localized detail
        wrapped in the standard ApiResponse envelope."""
    from app.i18n.locale import resolve_locale

    locale = resolve_locale(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(localize_detail(str(exc.detail), locale)).model_dump(),
    )


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    """Middleware that times each request and reports the duration to the client.

    Args:
        request: The incoming request.
        call_next: The next handler in the middleware chain.

    Returns:
        The response, with an added X-Process-Time-Ms header."""
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    return response


app.include_router(youtube_router, prefix="/ai", tags=["YouTube AI"])
app.include_router(agent_router, prefix="/ai", tags=["Agent"])
app.include_router(history_router, prefix="/ai", tags=["History"])
app.include_router(admin_router, prefix="/ai", tags=["Admin"])
app.include_router(auth_router, prefix="/ai", tags=["Auth"])
app.include_router(runtime_router, prefix="/ai", tags=["Runtime"])


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint reporting overall status and per-dependency checks."""
    checks = await collect_checks()
    return ApiResponse.ok({"service": "ai-layer", "healthy": is_healthy(checks), "checks": checks})
