from dotenv import load_dotenv
load_dotenv()
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import app.config.settings as settings
from app.exceptions import AiLayerConfigError, AiLayerError
from app.api.movies import router as movies_router
from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.history import router as history_router
from app.api.utilities import router as utilities_router
from app.api.youtube import router as youtube_router
from app.config.logger import Logger
from app.middleware.ip_address import GeoIPMiddleware
from app.middleware.rate_limit import RateLimitExceeded, limiter, rate_limit_exceeded_handler
from app.schemas.response import ApiResponse
from app.services.health import collect_checks, is_healthy
Logger.setup(level=settings.LOG_LEVEL)
logger = Logger.get(__name__)
_ingest_worker_task: Optional[asyncio.Task] = None
_config_refresh_task: Optional[asyncio.Task] = None

async def _remote_config_refresher() -> None:
    """(Nội bộ) Remote config refresher (async).

    Returns:
        (None) Kết quả trả về."""
    from app.config.remote import load_and_apply
    while True:
        await asyncio.sleep(max(settings.REMOTE_CONFIG_TTL, 1) * 60)
        try:
            await load_and_apply()
            logger.info('[remote_config] refreshed')
        except Exception as exc:
            logger.warning('[remote_config] refresh failed: %s', exc)

async def _start_config_refresher() -> None:
    """(Nội bộ) Bắt đầu config refresher (async).

    Returns:
        (None) Kết quả trả về."""
    global _config_refresh_task
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    _config_refresh_task = asyncio.create_task(_remote_config_refresher(), name='config-refresher')

async def _stop_config_refresher() -> None:
    """(Nội bộ) Dừng config refresher (async).

    Returns:
        (None) Kết quả trả về."""
    global _config_refresh_task
    if _config_refresh_task is None:
        return
    _config_refresh_task.cancel()
    try:
        await _config_refresh_task
    except asyncio.CancelledError:
        pass
    _config_refresh_task = None

async def _start_inline_ingest_worker() -> None:
    """(Nội bộ) Bắt đầu inline ingest worker (async).

    Returns:
        (None) Kết quả trả về."""
    global _ingest_worker_task
    if not settings.INGEST_ENABLED or not settings.RABBITMQ_URL:
        return
    if not settings.INGEST_WORKER_INLINE:
        logger.info('[startup] ingest worker inline disabled (INGEST_WORKER_INLINE=false)')
        return
    from app.ingest.consumer.worker import run_consumer
    _ingest_worker_task = asyncio.create_task(run_consumer(), name='ingest-worker')
    logger.info('[startup] ingest worker inline started')

async def _stop_inline_ingest_worker() -> None:
    """(Nội bộ) Dừng inline ingest worker (async).

    Returns:
        (None) Kết quả trả về."""
    global _ingest_worker_task
    if _ingest_worker_task is None:
        return
    _ingest_worker_task.cancel()
    try:
        await _ingest_worker_task
    except asyncio.CancelledError:
        pass
    _ingest_worker_task = None
    logger.info('[shutdown] ingest worker inline stopped')

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan `lifespan` (async).

    Args:
        _app: (FastAPI) Tham số `_app`."""
    Logger.sync_uvicorn(settings.LOG_LEVEL)
    logger.info('[startup] loading remote config')
    from app.config.remote import load_and_apply
    await load_and_apply()
    if not settings.API_KEYS:
        raise AiLayerConfigError('API_KEYS must be set before starting ai-layer')
    if not settings.DATA_MINER_URL or not settings.DATA_MINER_KEY:
        raise AiLayerConfigError('DATA_MINER_URL and DATA_MINER_KEY must be configured')
    if settings.APP_ENV != 'development' and not settings.DATA_MINER_SERVICE_TOKEN:
        raise AiLayerConfigError('DATA_MINER_SERVICE_TOKEN must be configured')
    from app.cache.client import get_redis
    from app.config.db.session import close_engine, init_db
    try:
        await init_db()
    except Exception as exc:
        logger.error('[db] init failed: %s', exc)
        raise AiLayerConfigError(f'Database initialization failed: {exc}', cause=exc) from exc
    await get_redis()
    await _start_config_refresher()
    from app.ingest.producer.publisher import close_producer, init_producer
    await init_producer()
    await _start_inline_ingest_worker()
    yield
    await _stop_inline_ingest_worker()
    await _stop_config_refresher()
    from app.cache.client import close_redis
    from app.clients.data_miner import close_client as close_dm
    await close_producer()
    await close_dm()
    await close_engine()
    await close_redis()
app = FastAPI(title='AI Layer', description='AI-powered YouTube + TikTok analysis', version='1.0.0', debug=False, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.add_middleware(GeoIPMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

@app.exception_handler(AiLayerError)
async def ai_layer_error_handler(_request: Request, exc: AiLayerError) -> JSONResponse:
    """Global handler for ai-layer domain errors."""
    return JSONResponse(
        status_code=exc.http_status,
        content=ApiResponse.fail(exc.message).model_dump(),
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Http exception handler (async).

    Args:
        _request: (Request) Tham số `_request`.
        exc: (HTTPException) Tham số `exc`.

    Returns:
        (JSONResponse) Kết quả trả về."""
    return JSONResponse(status_code=exc.status_code, content=ApiResponse.fail(str(exc.detail)).model_dump())

@app.middleware('http')
async def add_process_time(request: Request, call_next):
    """Add process time (async).

    Args:
        request: (Request) Tham số `request`.
        call_next: (Any) Tham số `call_next`."""
    start = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Process-Time-Ms'] = str(round((time.perf_counter() - start) * 1000, 2))
    return response
app.include_router(youtube_router, prefix='/ai', tags=['YouTube AI'])
app.include_router(agent_router, prefix='/ai', tags=['Agent'])
app.include_router(utilities_router, prefix='/ai', tags=['Utilities'])
app.include_router(history_router, prefix='/ai', tags=['History'])
app.include_router(movies_router, prefix='/ai', tags=['Movies'])
app.include_router(admin_router, prefix='/ai', tags=['Admin'])

@app.get('/health', tags=['Health'])
async def health():
    """    Health `health` (async)."""
    checks = await collect_checks()
    return ApiResponse.ok({'service': 'ai-layer', 'healthy': is_healthy(checks), 'checks': checks})
