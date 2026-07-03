"""initial schema

Revision ID: 90c66f03b10a
Revises:
Create Date: 2026-06-25 10:57:54.720374

"""

from collections.abc import Sequence

from alembic import op
from app.config.db.models import Base

revision: str = "90c66f03b10a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind, checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
