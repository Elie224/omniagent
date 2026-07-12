"""initial schema: user_memory + vector_memory

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_memory",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_user_memory_user_key", "user_memory", ["user_id", "key"])

    op.create_table(
        "vector_memory",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("doc_type", sa.String(64), nullable=False, index=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("embedding", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_index("ix_user_memory_user_key", table_name="user_memory")
    op.drop_table("user_memory")
    op.drop_table("vector_memory")
