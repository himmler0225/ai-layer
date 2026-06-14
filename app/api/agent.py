from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal, Optional

from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.services.agent import run_agent, run_agent_stream
from app.tools.definitions import TOOL_SETS
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/agent", dependencies=[Depends(verify_api_key)])


class AgentRequest(BaseModel):
    task:     str                                  = Field(..., description="Natural language task")
    tools:    Literal["youtube", "tiktok", "all"] = Field("all")
    max_iter: int                                  = Field(10, ge=1, le=20)
    system:   Optional[str]                        = Field(None)


@router.post("/run")
@limiter.limit("10/minute")
async def run(request: Request, body: AgentRequest):
    tools  = TOOL_SETS.get(body.tools, TOOL_SETS["all"])
    kwargs = {"system": body.system} if body.system else {}
    try:
        return ApiResponse.ok(await run_agent(body.task, tools, max_iter=body.max_iter, **kwargs))
    except RuntimeError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/stream")
@limiter.limit("10/minute")
async def run_stream(request: Request, body: AgentRequest):  # noqa: ARG001
    tools  = TOOL_SETS.get(body.tools, TOOL_SETS["all"])
    kwargs = {"system": body.system} if body.system else {}

    async def generate():
        try:
            async for chunk in run_agent_stream(body.task, tools, max_iter=body.max_iter, **kwargs):
                yield chunk
        except Exception as e:
            import json
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
