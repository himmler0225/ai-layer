from __future__ import annotations

import asyncio
import base64
import io
from functools import partial
from typing import Literal

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

from app.config.logger import Logger

logger = Logger.get(__name__)

ColorTheme = Literal["default", "green", "dark"]

_THEMES: dict[str, dict] = {
    "default": {"fill_color": "#000000", "back_color": "#ffffff"},
    "green":   {"fill_color": "#0d6e4e", "back_color": "#ffffff"},
    "dark":    {"fill_color": "#ffffff", "back_color": "#1a1a1a"},
}

def _generate_sync(url: str, size: int, theme: ColorTheme, rounded: bool) -> dict:
    colors = _THEMES.get(theme, _THEMES["default"])
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=size, border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage if rounded else None,
        module_drawer=RoundedModuleDrawer() if rounded else None,
        fill_color=colors["fill_color"],
        back_color=colors["back_color"],
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"url": url, "image": f"data:image/png;base64,{b64}", "theme": theme, "size": size}

async def generate_qr(url: str, size: int = 10, theme: ColorTheme = "default", rounded: bool = True) -> dict:
    logger.info("Generating QR for: %s (theme=%s)", url[:60], theme)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_generate_sync, url, size, theme, rounded))
