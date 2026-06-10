from dotenv import load_dotenv
load_dotenv()

from app.config.settings import LOG_LEVEL
from app.config.logger import Logger
Logger.setup(level=LOG_LEVEL)

import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from app.api.youtube import router as youtube_router
from app.api.agent import router as agent_router
from app.api.utilities import router as utilities_router
from app.middleware import limiter, rate_limit_exceeded_handler, RateLimitExceeded
from app.schemas.response import ApiResponse

app = FastAPI(
    title="AI Layer",
    description="AI-powered YouTube + TikTok analysis",
    version="1.0.0",
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
    took = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(took)
    return response


app.include_router(youtube_router,   prefix="/ai", tags=["YouTube AI"])
app.include_router(agent_router,     prefix="/ai", tags=["Agent"])
app.include_router(utilities_router, prefix="/ai", tags=["Utilities"])


@app.get("/health", tags=["Health"])
async def health():
    return ApiResponse.ok({"service": "ai-layer"})
