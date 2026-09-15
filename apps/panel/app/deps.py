from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import db


@dataclass
class SessionUser:
    user_id: UUID
    email: str
    name: str | None
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    role: str
    plan: str


def get_session_user(request: Request) -> SessionUser | None:
    raw = request.session.get("user")
    if not raw:
        return None
    try:
        return SessionUser(
            user_id=UUID(raw["user_id"]),
            email=raw["email"],
            name=raw.get("name"),
            tenant_id=UUID(raw["tenant_id"]),
            tenant_name=raw["tenant_name"],
            tenant_slug=raw["tenant_slug"],
            role=raw.get("role", "owner"),
            plan=raw.get("plan", "free"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def require_user(request: Request) -> SessionUser:
    user = get_session_user(request)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def login_redirect(request: Request):
    """Dependency-friendly guard that redirects instead of 401 JSON."""
    user = get_session_user(request)
    if user is None:
        return None
    return user


CurrentUser = Annotated[SessionUser, Depends(require_user)]


def set_session(request: Request, user: SessionUser) -> None:
    request.session["user"] = {
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "tenant_id": str(user.tenant_id),
        "tenant_name": user.tenant_name,
        "tenant_slug": user.tenant_slug,
        "role": user.role,
        "plan": user.plan,
    }
    # compat com templates antigos
    request.session["user_email"] = user.email
    request.session["tenant_name"] = user.tenant_name
    request.session["tenant_slug"] = user.tenant_slug


def load_membership(email: str) -> SessionUser | None:
    row = db.fetch_one(
        """
        SELECT u.id AS user_id, u.email, u.name, u.password_hash,
               t.id AS tenant_id, t.name AS tenant_name, t.slug AS tenant_slug,
               t.plan, m.role
        FROM agente.users u
        JOIN agente.memberships m ON m.user_id = u.id
        JOIN agente.tenants t ON t.id = m.tenant_id
        WHERE lower(u.email) = lower(%s) AND t.status = 'active'
        ORDER BY m.created_at
        LIMIT 1
        """,
        (email,),
    )
    if not row:
        return None
    return SessionUser(
        user_id=row["user_id"],
        email=row["email"],
        name=row["name"],
        tenant_id=row["tenant_id"],
        tenant_name=row["tenant_name"],
        tenant_slug=row["tenant_slug"],
        role=row["role"],
        plan=row["plan"],
    )


def password_hash_for(email: str) -> str | None:
    row = db.fetch_one(
        "SELECT password_hash FROM agente.users WHERE lower(email) = lower(%s)",
        (email,),
    )
    return row["password_hash"] if row else None


def redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)
