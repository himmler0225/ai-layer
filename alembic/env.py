"""Alembic environment for async SQLAlchemy migrations; resolves the database URL from DATABASE_URL."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.config.settings as settings
from alembic import context
from app.config.db.models import Base  # noqa: F401 — registers all tables on metadata
from app.config.db.url import resolve_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _engine_config() -> tuple[str, dict]:
    url = settings.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return resolve_database_url(url)


def run_migrations_offline() -> None:
    async_url, _ = _engine_config()
    context.configure(
        url=async_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    async_url, connect_args = _engine_config()
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = async_url
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
