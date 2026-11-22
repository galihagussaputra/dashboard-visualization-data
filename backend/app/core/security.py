import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import AuthSession, Role, User, UserRole

PBKDF2_ITERATIONS = 120_000


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    email: str
    display_name: str
    roles: frozenset[str]
    session_id: int


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    salt_part = base64.b64encode(salt).decode("ascii")
    hash_part = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_part}${hash_part}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_part, hash_part = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_part)
        expected = base64.b64decode(hash_part)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations_text)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalars(select(User).where(User.email == email.lower())).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: User, request_context: dict | None = None) -> str:
    token = secrets.token_urlsafe(32)
    ttl = get_settings().session_ttl_minutes
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl),
        request_context=request_context or {},
    )
    db.add(session)
    db.flush()
    return token


def revoke_session(db: Session, session_id: int) -> None:
    session = db.get(AuthSession, session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)


def bootstrap_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    roles: tuple[str, ...] | list[str],
) -> User:
    user = db.scalars(select(User).where(User.email == email.lower())).first()
    if user is None:
        user = User(
            email=email.lower(),
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()
    elif not verify_password(password, user.password_hash):
        user.password_hash = hash_password(password)
    user.display_name = display_name
    user.is_active = True

    for role_name in roles:
        role = db.scalars(select(Role).where(Role.name == role_name)).first()
        if role is None:
            role = Role(name=role_name, description=f"M2 {role_name} role")
            db.add(role)
            db.flush()
        existing = db.get(UserRole, (user.id, role.id))
        if existing is None:
            db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def user_roles(db: Session, user_id: int) -> frozenset[str]:
    rows = db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    ).all()
    return frozenset(row[0] for row in rows)


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    session = db.scalars(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    ).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return AuthenticatedUser(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user_roles(db, user.id),
        session_id=session.id,
    )


def require_roles(*allowed: str) -> Callable:
    def dependency(current: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not current.roles.intersection(allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return current

    return dependency
