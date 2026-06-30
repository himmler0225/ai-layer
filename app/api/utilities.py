from typing import Literal
from fastapi import APIRouter, Depends, Request
from app.exceptions import AiLayerUpstreamError
from pydantic import BaseModel, HttpUrl
from app.config.rate_limits import qr_rate_limit, shorten_rate_limit
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
from app.schemas.response import ApiResponse
from app.utilities.qr_generator import generate_qr
from app.utilities.url_shortener import shorten_url
router = APIRouter(prefix='/utilities', dependencies=[Depends(verify_api_key)])

class ShortenRequest(BaseModel):
    """    Lớp `ShortenRequest` (kế thừa BaseModel)."""
    url: HttpUrl
    provider: Literal['tinyurl', 'isgd'] = 'tinyurl'

class QRRequest(BaseModel):
    """    Lớp `QRRequest` (kế thừa BaseModel)."""
    url: HttpUrl
    size: int = 10
    theme: Literal['default', 'green', 'dark'] = 'default'
    rounded: bool = True

@router.post('/shorten', summary='Rút gọn URL')
@limiter.limit(shorten_rate_limit)
async def shorten(request: Request, body: ShortenRequest):
    """Shorten `shorten` (async).

    Args:
        request: (Request) Tham số `request`.
        body: (ShortenRequest) Tham số `body`."""
    result = await shorten_url(str(body.url), provider=body.provider)
    if 'error' in result:
        raise AiLayerUpstreamError(result['error'])
    return ApiResponse.ok(result)

@router.post('/qr', summary='Tạo mã QR từ URL')
@limiter.limit(qr_rate_limit)
async def qr_code(request: Request, body: QRRequest):
    """Qr code (async).

    Args:
        request: (Request) Tham số `request`.
        body: (QRRequest) Tham số `body`."""
    return ApiResponse.ok(await generate_qr(url=str(body.url), size=body.size, theme=body.theme, rounded=body.rounded))
