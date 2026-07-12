"""Modeles SQLAlchemy pour la persistance.

Tables :
- user_memory       : preferences/cles par (tenant_id, user_id, key)
- vector_memory     : embeddings par (tenant_id, key) avec namespace doc_type
- idempotency_keys  : reponses cachees par cle + tenant_id
- organizations     : tenants
- users             : comptes utilisateurs
- memberships       : (user_id, org_id, role)
- refresh_tokens    : JWT refresh avec rotation et revocation
- api_keys          : cles d API pour acces machine-to-machine (V2)

Multi-tenant : toutes les tables metier portent `tenant_id` (FK sur organizations).
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, Index, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from omniagent.core.database import Base


# ----------------------------------------------------------------------
# Memoires (avec tenant_id obligatoire)
# ----------------------------------------------------------------------
class UserMemoryRow(Base):
    __tablename__ = "user_memory"

    key:        Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id:  Mapped[str] = mapped_column(String(64), index=True)
    user_id:    Mapped[str] = mapped_column(String(64), index=True)
    value:      Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (Index("ix_user_memory_tenant_user_key", "tenant_id", "user_id", "key"),)


class VectorMemoryRow(Base):
    __tablename__ = "vector_memory"

    key:        Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id:  Mapped[str] = mapped_column(String(64), index=True)
    doc_type:   Mapped[str] = mapped_column(String(64), index=True)
    text:       Mapped[str] = mapped_column(Text)
    metadata_:  Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    # Embedding stocke en JSON (liste[float]) - remplacable par pgvector en prod.
    embedding:  Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_vector_memory_tenant_doc", "tenant_id", "doc_type"),)


class IdempotencyKeyRow(Base):
    __tablename__ = "idempotency_keys"

    key:            Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id:      Mapped[str] = mapped_column(String(64), index=True)
    request_hash:   Mapped[str] = mapped_column(String(64), index=True)
    status_code:    Mapped[int]
    body:           Mapped[dict] = mapped_column(JSON)
    created_at:     Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at:     Mapped[datetime] = mapped_column(DateTime, index=True)


# ----------------------------------------------------------------------
# Auth & multi-tenant
# ----------------------------------------------------------------------
class OrganizationRow(Base):
    """Tenant (= organisation cliente)."""
    __tablename__ = "organizations"

    org_id:     Mapped[str] = mapped_column(String(64), primary_key=True)
    name:       Mapped[str] = mapped_column(String(255))
    plan:       Mapped[str] = mapped_column(String(32), default="free")
    status:     Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_:  Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class UserRow(Base):
    """Compte utilisateur. Peut appartenir a plusieurs organisations via Membership."""
    __tablename__ = "users"

    user_id:       Mapped[str] = mapped_column(String(64), primary_key=True)
    email:         Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name:  Mapped[str] = mapped_column(String(255), default="")
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin:      Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MembershipRow(Base):
    """Liaison user <-> organization avec role par org."""
    __tablename__ = "memberships"

    membership_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id:        Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), index=True)
    org_id:         Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), index=True)
    role:           Mapped[str] = mapped_column(String(32), default="user")
    created_at:     Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_memberships_user_org", "user_id", "org_id", unique=True),)


class RefreshTokenRow(Base):
    """Refresh token JWT (rotation + revocation)."""
    __tablename__ = "refresh_tokens"

    token_id:     Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id:      Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), index=True)
    org_id:       Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), index=True)
    token_hash:   Mapped[str] = mapped_column(String(64), index=True)
    expires_at:   Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by:  Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_refresh_tokens_user_org", "user_id", "org_id"),)


class ApiKeyRow(Base):
    """Cle d API (machine-to-machine). Hash du secret en base."""
    __tablename__ = "api_keys"

    key_id:     Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id:     Mapped[str] = mapped_column(String(64), ForeignKey("organizations.org_id"), index=True)
    name:       Mapped[str] = mapped_column(String(255))
    secret_hash:Mapped[str] = mapped_column(String(64))
    scopes:     Mapped[list] = mapped_column(JSON, default=list)
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLogRow(Base):
    """Log d audit RGPD. Scope : (tenant_id, user_id, timestamp)."""
    __tablename__ = "audit_log"

    log_id:     Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id:  Mapped[str] = mapped_column(String(64), index=True)
    user_id:    Mapped[str] = mapped_column(String(64), index=True)
    action:     Mapped[str] = mapped_column(String(64), index=True)
    payload:    Mapped[dict] = mapped_column(JSON, default=dict)
    ip:         Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_audit_log_tenant_user_ts", "tenant_id", "user_id", "created_at"),)
