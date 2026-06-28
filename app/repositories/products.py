from __future__ import annotations

"""CRUD bảng products."""


from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.config.db.models import Product
from app.config.db.session import get_session_factory
from app.config.db.utils import model_to_dict


async def get_product(product_id: str) -> Optional[dict]:
    """Lấy một sản phẩm theo id."""
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Product).where(Product.id == product_id))
        return model_to_dict(row) if row else None


async def exists_product(product_id: str) -> bool:
    """Kiểm tra sản phẩm đã có trong DB."""
    factory = await get_session_factory()
    async with factory() as session:
        row = await session.scalar(select(Product.id).where(Product.id == product_id))
        return row is not None


async def upsert_product(
    *,
    id: str,
    name: str,
    platform: str = "mixed",
    metadata: dict | None = None,
) -> None:
    """Insert hoặc cập nhật metadata sản phẩm."""
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(Product).values(
            id=id,
            name=name,
            platform=platform,
            metadata_=metadata or {},
        )
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[Product.id],
            set_={
                "name": excluded.name,
                "platform": excluded.platform,
                "metadata": excluded.metadata,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()


async def list_products(*, platform: str | None = None, limit: int = 50) -> list[dict]:
    """Liệt kê sản phẩm (mới nhất trước)."""
    factory = await get_session_factory()
    async with factory() as session:
        q = select(Product).order_by(Product.updated_at.desc()).limit(limit)
        if platform:
            q = q.where(Product.platform == platform)
        rows = (await session.execute(q)).scalars().all()
        return [model_to_dict(row) for row in rows]
