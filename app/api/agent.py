from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
import app.config.settings as settings
from app.config.logger import Logger
from app.config.rate_limits import agent_rate_limit
from app.exceptions import AiLayerError
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.schemas.response import ApiResponse
from app.services.agent.core import run_agent_multi, run_agent_multi_stream
from app.services.agent.domains import DOMAIN_IDS
from app.utils.llm_errors import log_error

logger = Logger.get(__name__)
router = APIRouter(prefix="/agent", dependencies=[Depends(verify_api_key)])

_VALID_TOOL_SETS = (*DOMAIN_IDS, "all")


class AgentRequest(BaseModel):
    """Request body for running the multi-tool agent: the task, tool set, iteration cap, and optional system prompt override."""

    task: str = Field(..., description="Natural language task")
    tools: str = Field("all", description=f"One of: {', '.join(_VALID_TOOL_SETS)}")
    max_iter: int | None = Field(None, ge=1, le=20, description="Defaults to AGENT_MAX_ITER from remote config")
    system: str | None = Field(None)

    @field_validator("tools")
    @classmethod
    def _validate_tools(cls, v: str) -> str:
        if v not in _VALID_TOOL_SETS:
            raise ValueError(f"tools phải là một trong: {', '.join(_VALID_TOOL_SETS)}")
        return v


@router.post("/run")
@limiter.limit(agent_rate_limit)
async def run(request: Request, body: AgentRequest):
    """Run the multi-tool agent to completion and return its final result.

    Args:
        request: Incoming request, used for rate limiting.
        body: Task description, tool set, and iteration parameters.

    Returns:
        ApiResponse wrapping the agent's final result."""
    max_iter = body.max_iter or settings.AGENT_MAX_ITER
    kwargs = {"system": body.system} if body.system else {}
    return ApiResponse.ok(await run_agent_multi(body.task, body.tools, max_iter, **kwargs))


@router.post("/run/stream")
@limiter.limit(agent_rate_limit)
async def run_stream(request: Request, body: AgentRequest):
    """Run the multi-tool agent and stream its progress as Server-Sent Events.

    Args:
        request: Incoming request, used for rate limiting.
        body: Task description, tool set, and iteration parameters.

    Returns:
        A StreamingResponse emitting SSE chunks from the agent run."""
    max_iter = body.max_iter or settings.AGENT_MAX_ITER
    kwargs = {"system": body.system} if body.system else {}

    async def generate():
        """Yield SSE-formatted chunks from the agent stream, converting AiLayerError and any
        unexpected exception into a localized SSE error event instead of propagating them."""
        from app.i18n.responses import client_message

        try:
            async for chunk in run_agent_multi_stream(body.task, body.tools, max_iter, **kwargs):
                yield chunk
        except AiLayerError as e:
            import json

            detail = client_message(e)
            yield f"data: {json.dumps({'type': 'error', 'detail': detail, 'message': detail}, ensure_ascii=False)}\n\n"
        except Exception as e:
            import json

            from app.i18n import msg

            log_error(logger, e, where="agent_stream unhandled")
            detail = msg("errors.generic")
            yield f"data: {json.dumps({'type': 'error', 'detail': detail, 'message': detail}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
