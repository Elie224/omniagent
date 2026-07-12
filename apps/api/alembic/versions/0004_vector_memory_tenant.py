"""Tenant isolation hardening for vector_memory.

- Backfill tenant_id=default for legacy rows
- Make tenant_id NOT NULL
- Add composite index (tenant_id, key) for fast scoped search
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_vector_memory_tenant"
down_revision = "0003_auth_and_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Backfill (idempotent : WHERE tenant_id IS NULL)
    op.execute("UPDATE vector_memory SET tenant_id = '"'default'"' WHERE tenant_id IS NULL")
    # 2) NOT NULL
    op.alter_column("vector_memory", "tenant_id", existing_type=sa.String(64), nullable=False)
    # 3) Composite index
    op.create_index("ix_vector_memory_tenant_key", "vector_memory", ["tenant_id", "key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vector_memory_tenant_key", table_name="vector_memory")
    op.alter_column("vector_memory", "tenant_id", existing_type=sa.String(64), nullable=True)