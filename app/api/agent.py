from typing import Literal, Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import app.config.settings as settings
from app.config.rate_limits import agent_rate_limit
from app.exceptions import AiLayerError
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.schemas.response import ApiResponse
from app.services.agent.runner import run_agent
from app.services.agent.stream import run_agent_stream
from app.tools.definitions import TOOL_SETS

router = APIRouter(prefix='/agent', dependencies=[Depends(verify_api_key)])

class AgentRequest(BaseModel):
    """    Lớp `AgentRequest` (kế thừa BaseModel)."""
    task: str = Field(..., description='Natural language task')
    tools: Literal['youtube', 'tiktok', 'movies', 'all'] = Field('all')
    max_iter: Optional[int] = Field(None, ge=1, le=20, description='Defaults to AGENT_MAX_ITER from remote config')
    system: Optional[str] = Field(None)

@router.post('/run')
@limiter.limit(agent_rate_limit)
async def run(request: Request, body: AgentRequest):
    """Chạy `run` (async).

    Args:
        request: (Request) Tham số `request`.
        body: (AgentRequest) Tham số `body`."""
    tools = TOOL_SETS.get(body.tools, TOOL_SETS['all'])
    max_iter = body.max_iter or settings.AGENT_MAX_ITER
    kwargs = {'system': body.system} if body.system else {}
    return ApiResponse.ok(await run_agent(body.task, tools, max_iter=max_iter, **kwargs))

@router.post('/run/stream')
@limiter.limit(agent_rate_limit)
async def run_stream(request: Request, body: AgentRequest):
    """Chạy stream (async).

    Args:
        request: (Request) Tham số `request`.
        body: (AgentRequest) Tham số `body`."""
    tools = TOOL_SETS.get(body.tools, TOOL_SETS['all'])
    max_iter = body.max_iter or settings.AGENT_MAX_ITER
    kwargs = {'system': body.system} if body.system else {}

    async def generate():
        """    Generate `generate` (async)."""
        try:
            async for chunk in run_agent_stream(body.task, tools, max_iter=max_iter, **kwargs):
                yield chunk
        except AiLayerError as e:
            import json
            yield f"data: {json.dumps({'type': 'error', 'message': e.message})}\n\n"
        except Exception as e:
            import json
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    return StreamingResponse(generate(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
