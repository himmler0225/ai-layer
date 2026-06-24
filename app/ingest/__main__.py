"""Entry point ingest-worker: python -m app.ingest"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

load_dotenv()

import app.config.settings as settings
from app.config.logger import Logger
from app.config.remote import load_and_apply
from app.db.session import close_engine, init_db
from app.ingest.broker import close_broker
from app.ingest.consumer import run_consumer

logger = Logger.get(__name__)


async def main() -> None:
    """Khởi động ingest-worker."""
    Logger.setup(level=settings.LOG_LEVEL)
    logger.info("[ingest-worker] starting")
    await load_and_apply()
    await init_db()
    try:
        await run_consumer()
    finally:
        await close_broker()
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
