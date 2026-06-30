"""rename product RAG tables/columns to movie"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "90c66f03b10a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'products'
          ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'movies'
          ) THEN
            ALTER TABLE products RENAME TO movies;
          END IF;
        END $$;
        """
    )
    for table in ("raw_reviews", "curated_reviews", "aspect_chunks", "aspect_summaries"):
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = '{table}' AND column_name = 'product_id'
              ) THEN
                ALTER TABLE {table} RENAME COLUMN product_id TO movie_id;
              END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for table in ("raw_reviews", "curated_reviews", "aspect_chunks", "aspect_summaries"):
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = '{table}' AND column_name = 'movie_id'
              ) THEN
                ALTER TABLE {table} RENAME COLUMN movie_id TO product_id;
              END IF;
            END $$;
            """
        )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'movies'
          ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'products'
          ) THEN
            ALTER TABLE movies RENAME TO products;
          END IF;
        END $$;
        """
    )
