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

Logger.setup(level=settings.LOG_LEVEL)
logger = Logger.get(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("[startup] loading remote config")
    from app.config.remote import load_and_apply
    await load_and_apply()

    if not settings.API_KEYS:
        raise RuntimeError("API_KEYS must be set before starting ai-layer")

    from app.db.session import init_db, close_engine
    from app.cache.client import get_redis

    try:
        await init_db()
    except Exception as exc:
        Logger.get(__name__).warning("[db] init failed: %s", exc)

    await get_redis()

    yield

    from app.clients.data_miner import close_client as close_dm
    from app.cache.client import close_redis
    from app.db.mongo import close_mongo

    await close_dm()
    await close_engine()
    await close_redis()
    await close_mongo()

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(str(exc.detail)).model_dump(),
    )

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(
        round((time.perf_counter() - start) * 1000, 2)
    )
    return response

app.include_router(youtube_router,   prefix="/ai", tags=["YouTube AI"])
app.include_router(agent_router,     prefix="/ai", tags=["Agent"])
app.include_router(utilities_router, prefix="/ai", tags=["Utilities"])
app.include_router(history_router,   prefix="/ai", tags=["History"])

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