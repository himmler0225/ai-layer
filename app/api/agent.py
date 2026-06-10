from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal, Optional

from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.services.agent import run_agent
from app.tools.definitions import TOOL_SETS
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/agent", dependencies=[Depends(verify_api_key)])


class AgentRequest(BaseModel):
    task:     str                                  = Field(..., description="Natural language task")
    tools:    Literal["youtube", "tiktok", "all"] = Field("all")
    max_iter: int                                  = Field(5, ge=1, le=20)
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
