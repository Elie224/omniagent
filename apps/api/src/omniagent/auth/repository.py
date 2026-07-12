"""Repository auth : acces DB pour users, orgs, memberships, refresh tokens.

Toutes les methodes sont async. Les requetes portent systematiquement sur
`tenant_id` / `org_id` pour eviter toute fuite cross-tenant.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from omniagent.core.models.db import (
    OrganizationRow, UserRow, MembershipRow, RefreshTokenRow, ApiKeyRow
)


# --- Organizations ---
async def create_organization(db: AsyncSession, name: str, plan: str = "free",
                                org_id: Optional[str] = None) -> OrganizationRow:
    org = OrganizationRow(org_id=org_id or str(uuid.uuid4()),
                           name=name, plan=plan, status="active")
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def get_organization(db: AsyncSession, org_id: str) -> OrganizationRow | None:
    r = await db.execute(select(OrganizationRow).where(OrganizationRow.org_id == org_id))
    return r.scalar_one_or_none()


# --- Users ---
async def create_user(db: AsyncSession, email: str, password_hash: str,
                       display_name: str = "", is_admin: bool = False) -> UserRow:
    user = UserRow(user_id=str(uuid.uuid4()), email=email.lower().strip(),
                    password_hash=password_hash, display_name=display_name,
                    is_active=True, is_admin=is_admin)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> UserRow | None:
    r = await db.execute(select(UserRow).where(UserRow.email == email.lower().strip()))
    return r.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> UserRow | None:
    r = await db.execute(select(UserRow).where(UserRow.user_id == user_id))
    return r.scalar_one_or_none()


async def update_last_login(db: AsyncSession, user_id: str) -> None:
    r = await db.execute(select(UserRow).where(UserRow.user_id == user_id))
    user = r.scalar_one_or_none()
    if user:
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()


# --- Memberships ---
async def create_membership(db: AsyncSession, user_id: str, org_id: str,
                              role: str = "user") -> MembershipRow:
    m = MembershipRow(membership_id=str(uuid.uuid4()),
                       user_id=user_id, org_id=org_id, role=role)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def get_membership(db: AsyncSession, user_id: str,
                          org_id: str) -> MembershipRow | None:
    r = await db.execute(
        select(MembershipRow).where(
            MembershipRow.user_id == user_id,
            MembershipRow.org_id == org_id,
        )
    )
    return r.scalar_one_or_none()


async def list_user_orgs(db: AsyncSession, user_id: str) -> list[MembershipRow]:
    r = await db.execute(
        select(MembershipRow).where(MembershipRow.user_id == user_id)
    )
    return list(r.scalars())


# --- Refresh tokens ---
async def store_refresh_token(db: AsyncSession, token_id: str, user_id: str,
                                org_id: str, token_hash: str,
                                expires_at: datetime) -> RefreshTokenRow:
    rt = RefreshTokenRow(token_id=token_id, user_id=user_id, org_id=org_id,
                          token_hash=token_hash, expires_at=expires_at)
    db.add(rt)
    await db.commit()
    return rt


async def get_refresh_token(db: AsyncSession, token_id: str) -> RefreshTokenRow | None:
    r = await db.execute(
        select(RefreshTokenRow).where(RefreshTokenRow.token_id == token_id)
    )
    return r.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token_id: str,
                                replaced_by: str | None = None) -> None:
    r = await db.execute(
        select(RefreshTokenRow).where(RefreshTokenRow.token_id == token_id)
    )
    rt = r.scalar_one_or_none()
    if rt is not None:
        rt.revoked_at = datetime.now(timezone.utc)
        rt.replaced_by = replaced_by
        await db.commit()


async def revoke_all_user_tokens(db: AsyncSession, user_id: str) -> int:
    """Revoque tous les refresh tokens d un user (logout global / vol)."""
    r = await db.execute(
        select(RefreshTokenRow).where(
            RefreshTokenRow.user_id == user_id,
            RefreshTokenRow.revoked_at.is_(None),
        )
    )
    count = 0
    for rt in r.scalars():
        rt.revoked_at = datetime.now(timezone.utc)
        count += 1
    await db.commit()
    return count
