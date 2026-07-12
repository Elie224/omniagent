"""idempotency_keys

Revision ID: 0002_idempotency_keys
Revises: 0001_initial
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_idempotency_keys"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("body", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_idempotency_keys_hash", "idempotency_keys", ["request_hash"])
    op.create_index("ix_idempotency_keys_expires", "idempotency_keys", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_expires", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_hash", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
