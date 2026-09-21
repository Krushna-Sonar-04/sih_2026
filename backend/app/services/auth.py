"""Local authentication and role-based access.

Roles: analyst < lead_analyst < admin.
  analyst      - create/view watches, view analysis, use the assistant, export
  lead_analyst - the above plus alert configuration
  admin        - the above plus users, sources, system health, audit log

The first administrator is provisioned from ADMIN_EMAIL / ADMIN_PASSWORD in
the environment. No credential is ever hard-coded or returned by the API.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import security
from ..config import get_settings
from ..database import get_db
from ..models import User

logger = logging.getLogger("drishti.auth")


def _settings():
    return get_settings()


def user_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(
    db: Session, email: str, password: str, role: str = "analyst", display_name: str = ""
) -> User:
    email = email.strip().lower()
    if role not in security.ROLES:
        raise ValueError(f"Unknown role '{role}'.")
    if get_by_email(db, email) is not None:
        raise ValueError("A user with that email already exists.")
    user = User(
        id=f"usr-{uuid.uuid4().hex[:10]}",
        email=email,
        display_name=display_name or email.split("@")[0],
        role=role,
        password_hash=security.hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def bootstrap_admin(db: Session) -> None:
    """Create the first admin from the environment when none exists."""
    settings = _settings()
    if not settings.admin_email or not settings.admin_password:
        return
    if get_by_email(db, settings.admin_email) is not None:
        return
    try:
        create_user(
            db,
            settings.admin_email,
            settings.admin_password,
            role="admin",
            display_name=settings.admin_name,
        )
        logger.info("Provisioned first administrator from environment configuration.")
    except Exception:  # pragma: no cover - never block startup
        db.rollback()
        logger.exception("Administrator bootstrap failed.")


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if user is None or not user.active:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return user


def issue_token(user: User) -> tuple[str, int]:
    settings = _settings()
    token = security.create_token(
        user.email, user.role, settings.jwt_secret, settings.jwt_expires_minutes
    )
    return token, settings.jwt_expires_minutes * 60


# --------------------------------------------------------------------------- dependencies
def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Resolve the bearer token when present. Returns None when anonymous."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    claims = security.decode_token(header[7:].strip(), _settings().jwt_secret)
    if not claims:
        return None
    return get_by_email(db, str(claims.get("sub", "")))


def actor_name(user: User | None) -> str:
    return user.email if user is not None else "anonymous"


def require_role(required: str):
    """Dependency factory enforcing a minimum role.

    When AUTH_REQUIRED is false (default for the offline demo) anonymous
    access is allowed, but a supplied token is still validated and its role
    still enforced.
    """

    def dependency(user: User | None = Depends(current_user)) -> User | None:
        settings = _settings()
        if user is None:
            if settings.auth_required:
                raise HTTPException(status_code=401, detail="Authentication required.")
            return None
        if not security.role_allows(user.role, required):
            raise HTTPException(
                status_code=403, detail=f"Role '{user.role}' is not permitted to perform this action."
            )
        return user

    return dependency
