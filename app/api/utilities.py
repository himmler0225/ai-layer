from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, HttpUrl
from typing import Literal

from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.utilities.url_shortener import shorten_url
from app.utilities.qr_generator import generate_qr
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/utilities", dependencies=[Depends(verify_api_key)])


class ShortenRequest(BaseModel):
    url:      HttpUrl
    provider: Literal["tinyurl", "isgd"] = "tinyurl"


class QRRequest(BaseModel):
    url:     HttpUrl
    size:    int                          = 10
    theme:   Literal["default", "green", "dark"] = "default"
    rounded: bool                         = True


@router.post("/shorten", summary="Rút gọn URL")
@limiter.limit("30/minute")
async def shorten(request: Request, body: ShortenRequest):
    result = await shorten_url(str(body.url), provider=body.provider)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return ApiResponse.ok(result)


@router.post("/qr", summary="Tạo mã QR từ URL")
@limiter.limit("20/minute")
async def qr_code(request: Request, body: QRRequest):
    try:
        return ApiResponse.ok(generate_qr(
            url=str(body.url), size=body.size, theme=body.theme, rounded=body.rounded,
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
