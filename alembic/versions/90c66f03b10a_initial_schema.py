"""initial schema

Revision ID: 90c66f03b10a
Revises:
Create Date: 2026-06-25 10:57:54.720374

"""

from typing import Sequence, Union

from alembic import op
from app.config.db.models import Base

revision: str = "90c66f03b10a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind, checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
