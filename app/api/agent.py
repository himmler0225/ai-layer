from typing import Literal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import app.config.settings as settings
from app.config.logger import Logger
from app.config.rate_limits import agent_rate_limit
from app.exceptions import AiLayerError
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.schemas.response import ApiResponse
from app.services.agent.core import run_agent_multi, run_agent_multi_stream
from app.utils.llm_errors import log_error

logger = Logger.get(__name__)
router = APIRouter(prefix="/agent", dependencies=[Depends(verify_api_key)])


class AgentRequest(BaseModel):
    """Lớp `AgentRequest` (kế thừa BaseModel)."""

    task: str = Field(..., description="Natural language task")
    tools: Literal["youtube", "tiktok", "movies", "all"] = Field("all")
    max_iter: int | None = Field(None, ge=1, le=20, description="Defaults to AGENT_MAX_ITER from remote config")
    system: str | None = Field(None)


@router.post("/run")
@limiter.limit(agent_rate_limit)
async def run(request: Request, body: AgentRequest):
    """Chạy `run` (async).

    Args:
        request: (Request) Tham số `request`.
        body: (AgentRequest) Tham số `body`."""
    max_iter = body.max_iter or settings.AGENT_MAX_ITER
    kwargs = {"system": body.system} if body.system else {}
    return ApiResponse.ok(await run_agent_multi(body.task, body.tools, max_iter, **kwargs))


@router.post("/run/stream")
@limiter.limit(agent_rate_limit)
async def run_stream(request: Request, body: AgentRequest):
    """Chạy stream (async).

    Args:
        request: (Request) Tham số `request`.
        body: (AgentRequest) Tham số `body`."""
    max_iter = body.max_iter or settings.AGENT_MAX_ITER
    kwargs = {"system": body.system} if body.system else {}

    async def generate():
        """Generate `generate` (async)."""
        from app.i18n.responses import client_message

        try:
            async for chunk in run_agent_multi_stream(body.task, body.tools, max_iter, **kwargs):
                yield chunk
        except AiLayerError as e:
            import json

            vi = client_message(e, "vi")
            en = client_message(e, "en")
            yield f"data: {json.dumps({'type': 'error', 'detail_vi': vi, 'detail_en': en, 'message': vi}, ensure_ascii=False)}\n\n"
        except Exception as e:
            import json

            from app.i18n import t

            log_error(logger, e, where="agent_stream unhandled")
            vi = t("errors.generic", "vi")
            en = t("errors.generic", "en")
            yield f"data: {json.dumps({'type': 'error', 'detail_vi': vi, 'detail_en': en, 'message': vi}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
