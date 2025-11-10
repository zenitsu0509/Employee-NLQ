from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251110_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (safe if already present)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Create table for document chunks with embedding vector. Adjust dimension if your embedding model differs.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id UUID PRIMARY KEY,
            document_id TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB,
            embedding vector(384)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS document_chunks;")
