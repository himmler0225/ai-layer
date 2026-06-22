from dotenv import load_dotenv
load_dotenv()

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.config.settings as settings
from app.config.logger import Logger
from app.schemas.response import ApiResponse

from app.middleware import limiter, rate_limit_exceeded_handler, RateLimitExceeded

# routers
from app.api.youtube import router as youtube_router
from app.api.agent import router as agent_router
from app.api.utilities import router as utilities_router
from app.api.history import router as history_router


# =========================
# LOGGER INIT
# =========================
Logger.setup(level=settings.LOG_LEVEL)


# =========================
# LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 1. LOAD REMOTE CONFIG FIRST (CRITICAL)
    from app.config.remote import load_and_apply
    await load_and_apply()

    # 2. validate API keys AFTER config load
    if not settings.API_KEYS:
        raise RuntimeError("API_KEYS must be set before starting ai-layer")

    # 3. init DB / cache
    from app.db.base import init_tables
    from app.cache.client import get_redis

    try:
        await init_tables()
    except Exception as e:
        import logging
        logging.getLogger("app.main").warning(
            "PostgreSQL init failed (app will still start): %s", e
        )

    await get_redis()

    yield

    # =========================
    # SHUTDOWN
    # =========================
    from app.clients.data_miner import close_client as close_dm
    from app.db.base import close_pool
    from app.cache.client import close_redis
    from app.db.mongo import close_mongo

    await close_dm()
    await close_pool()
    await close_redis()
    await close_mongo()


# =========================
# APP INIT
# =========================
app = FastAPI(
    title="AI Layer",
    description="AI-powered YouTube + TikTok analysis",
    version="1.0.0",
    debug=False,
    lifespan=lifespan,
)


# =========================
# MIDDLEWARE
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# =========================
# EXCEPTION HANDLER
# =========================
@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(str(exc.detail)).model_dump(),
    )


# =========================
# MIDDLEWARE (timing)
# =========================
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(
        round((time.perf_counter() - start) * 1000, 2)
    )
    return response


# =========================
# ROUTES
# =========================
app.include_router(youtube_router,   prefix="/ai", tags=["YouTube AI"])
app.include_router(agent_router,     prefix="/ai", tags=["Agent"])
app.include_router(utilities_router, prefix="/ai", tags=["Utilities"])
app.include_router(history_router,   prefix="/ai", tags=["History"])


# =========================
# HEALTH CHECK
# =========================
@app.get("/health", tags=["Health"])
async def health():
    import httpx

    checks: dict = {}

    # data miner
    try:
        r = await httpx.AsyncClient(timeout=3).get(
            f"{settings.DATA_MINER_URL}/health"
        )
        checks["data_miner"] = "ok" if r.is_success else f"status {r.status_code}"
    except Exception as e:
        checks["data_miner"] = f"unreachable: {e}"

    # openai key
    checks["openai_key"] = "set" if settings.OPENAI_API_KEY else "missing"

    healthy = (
        checks["data_miner"] == "ok"
        and checks["openai_key"] == "set"
    )

    return ApiResponse.ok(
        {
            "service": "ai-layer",
            "healthy": healthy,
            "checks": checks,
        }
    )