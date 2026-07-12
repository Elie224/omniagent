"""auth & multi-tenant : organizations, users, memberships, refresh_tokens, api_keys
+ ajout tenant_id sur user_memory, vector_memory, idempotency_keys

Revision ID: 0003_auth_and_tenant
Revises: 0002_idempotency_keys
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_auth_and_tenant"
down_revision = "0002_idempotency_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Nouvelles tables auth
    op.create_table(
        "organizations",
        sa.Column("org_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(32), server_default="free"),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("metadata", sa.JSON, server_default="{}"),
    )
    op.create_index("ix_organizations_org_id", "organizations", ["org_id"])

    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), server_default=""),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("membership_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.org_id"), nullable=False),
        sa.Column("role", sa.String(32), server_default="user"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_memberships_user_org", "memberships", ["user_id", "org_id"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.org_id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("replaced_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_org", "refresh_tokens", ["user_id", "org_id"])
    op.create_index("ix_refresh_tokens_hash", "refresh_tokens", ["token_hash"])

    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.org_id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("scopes", sa.JSON, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_api_keys_org", "api_keys", ["org_id"])

    # 1b) Audit log
    op.create_table(
        "audit_log",
        sa.Column("log_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, server_default="{}"),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_tenant_user_ts", "audit_log", ["tenant_id", "user_id", "created_at"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    # 2) Ajout de tenant_id sur les tables existantes (avec valeur par defaut)
    #    Pour la migration sans downtime, on ajoute la colonne nullable=True puis
    #    on remplit avec un tenant par defaut "legacy", puis on rend NOT NULL.
    with op.batch_alter_table("user_memory") as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(64), nullable=True))
        batch.create_index("ix_user_memory_tenant_user_key", ["tenant_id", "user_id", "key"])
    op.execute("UPDATE user_memory SET tenant_id = 'legacy' WHERE tenant_id IS NULL")
    with op.batch_alter_table("user_memory") as batch:
        batch.alter_column("tenant_id", nullable=False)

    with op.batch_alter_table("vector_memory") as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(64), nullable=True))
        batch.create_index("ix_vector_memory_tenant_doc", ["tenant_id", "doc_type"])
    op.execute("UPDATE vector_memory SET tenant_id = 'legacy' WHERE tenant_id IS NULL")
    with op.batch_alter_table("vector_memory") as batch:
        batch.alter_column("tenant_id", nullable=False)

    with op.batch_alter_table("idempotency_keys") as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(64), nullable=True))
    op.execute("UPDATE idempotency_keys SET tenant_id = 'legacy' WHERE tenant_id IS NULL")
    with op.batch_alter_table("idempotency_keys") as batch:
        batch.alter_column("tenant_id", nullable=False)
        batch.create_index("ix_idempotency_keys_tenant", ["tenant_id"])


def downgrade() -> None:
    with op.batch_alter_table("idempotency_keys") as batch:
        batch.drop_index("ix_idempotency_keys_tenant")
        batch.drop_column("tenant_id")
    with op.batch_alter_table("vector_memory") as batch:
        batch.drop_index("ix_vector_memory_tenant_doc")
        batch.drop_column("tenant_id")
    with op.batch_alter_table("user_memory") as batch:
        batch.drop_index("ix_user_memory_tenant_user_key")
        batch.drop_column("tenant_id")

    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_tenant_user_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_api_keys_org", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_refresh_tokens_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_org", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_memberships_user_org", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organizations_org_id", table_name="organizations")
    op.drop_table("organizations")
