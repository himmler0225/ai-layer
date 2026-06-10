from dotenv import load_dotenv
load_dotenv()

from app.config.settings import LOG_LEVEL, API_KEYS, CORS_ORIGINS
from app.config.logger import Logger
Logger.setup(level=LOG_LEVEL)

if not API_KEYS:
    raise RuntimeError("API_KEYS env var must be set before starting ai-layer")

import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.youtube import router as youtube_router
from app.api.agent import router as agent_router
from app.api.utilities import router as utilities_router
from app.middleware import limiter, rate_limit_exceeded_handler, RateLimitExceeded
from app.schemas.response import ApiResponse

@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    # Graceful shutdown — close shared HTTP clients
    from app.clients.data_miner import close_client as close_dm
    await close_dm()

app = FastAPI(
    title="AI Layer",
    description="AI-powered YouTube + TikTok analysis",
    version="1.0.0",
    debug=False,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    return response

app.include_router(youtube_router,   prefix="/ai", tags=["YouTube AI"])
app.include_router(agent_router,     prefix="/ai", tags=["Agent"])
app.include_router(utilities_router, prefix="/ai", tags=["Utilities"])

@app.get("/health", tags=["Health"])
async def health():
    import httpx
    from app.config.settings import DATA_MINER_URL, ANTHROPIC_API_KEY

    checks: dict = {}

    try:
        r = await httpx.AsyncClient(timeout=3).get(f"{DATA_MINER_URL}/health")
        checks["data_miner"] = "ok" if r.is_success else f"status {r.status_code}"
    except Exception as e:
        checks["data_miner"] = f"unreachable: {e}"

    checks["claude_key"] = "set" if ANTHROPIC_API_KEY else "missing"

    healthy = checks["data_miner"] == "ok" and checks["claude_key"] == "set"
    return ApiResponse.ok({"service": "ai-layer", "healthy": healthy, "checks": checks})
