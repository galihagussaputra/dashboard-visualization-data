from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import record_audit, request_context
from app.core.db import get_db
from app.core.security import (
    AuthenticatedUser,
    authenticate_user,
    create_session,
    get_current_user,
    revoke_session,
    user_roles,
)

from .schemas import LoginRequest, LoginResponse, UserRead

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate_user(db, payload.email.strip(), payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    context = request_context(request)
    token = create_session(db, user, context)
    record_audit(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=user.id,
        context=context,
    )
    db.commit()
    return LoginResponse(
        access_token=token,
        user=UserRead(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            roles=sorted(user_roles(db, user.id)),
        ),
    )


@router.post("/auth/logout")
def logout(
    request: Request,
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    revoke_session(db, current.session_id)
    record_audit(
        db,
        action="auth.logout",
        entity_type="user",
        entity_id=str(current.user_id),
        actor_id=current.user_id,
        context=request_context(request),
    )
    db.commit()
    return {"status": "logged_out"}


@router.get("/auth/me", response_model=UserRead)
def me(current: AuthenticatedUser = Depends(get_current_user)) -> UserRead:
    return UserRead(
        user_id=current.user_id,
        email=current.email,
        display_name=current.display_name,
        roles=sorted(current.roles),
    )
