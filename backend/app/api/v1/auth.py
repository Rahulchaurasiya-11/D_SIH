"""Authentication and user administration."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.core.ratelimit import client_key, login_limiter, register_limiter
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import repositories as repo
from app.deps import get_current_user, require_role
from app.models import (
    ROLE_LABELS,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    Role,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def to_public(user: Dict[str, Any]) -> UserPublic:
    return UserPublic(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user.get("role", Role.INSPECTOR.value),
        role_label=ROLE_LABELS.get(user.get("role", ""), ""),
        designation=user.get("designation", ""),
        jurisdiction=user.get("jurisdiction", ""),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )


def _issue(user: Dict[str, Any]) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user["id"], user.get("role", ""), user.get("full_name", "")),
        refresh_token=create_refresh_token(user["id"]),
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=to_public(user),
    )


def _enforce(limiter, key: str, message: str) -> None:
    allowed, retry_after = limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    """
    Self-registration always creates an INSPECTOR, whatever role the request asks
    for - otherwise anyone could mint themselves an admin account. Elevation is an
    admin action (`PATCH /auth/users/{id}/role`).

    Exception: when the user store is empty the very first account becomes ADMIN so
    a fresh deployment is reachable.
    """
    _enforce(register_limiter, client_key(request),
             "Too many accounts created from this address. Try again later.")

    if repo.users.by_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email address.",
        )

    role = Role.ADMIN.value if repo.users.count() == 0 else Role.INSPECTOR.value

    user = repo.users.create(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        designation=payload.designation,
        jurisdiction=payload.jurisdiction,
    )
    repo.audit_log.record(user["id"], user["full_name"], "USER_REGISTERED", user["id"], "role=%s" % role)
    return _issue(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request):
    # Limited twice on purpose. Per-IP stops a single host hammering the endpoint;
    # per-e-mail stops an attacker who rotates IPs (or spoofs X-Forwarded-For)
    # from brute-forcing one officer's account.
    email_key = payload.email.lower().strip()
    _enforce(login_limiter, client_key(request, "login"),
             "Too many sign-in attempts. Try again in a few minutes.")
    _enforce(login_limiter, "email:" + email_key,
             "Too many sign-in attempts for this account. Try again in a few minutes.")

    user = repo.users.by_email(payload.email)
    # Same message and code for "no such user" and "wrong password", so the endpoint
    # cannot be used to enumerate which officer accounts exist.
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    # A correct password clears the budget, so an officer who mistyped a few times
    # is not locked out for the rest of the window.
    login_limiter.reset(client_key(request, "login"))
    login_limiter.reset("email:" + email_key)

    repo.audit_log.record(user["id"], user.get("full_name", ""), "LOGIN", user["id"])
    return _issue(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest):
    claims = decode_token(payload.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has expired. Please sign in again.",
        )
    user = repo.users.by_id(claims["sub"])
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is no longer active.")
    return _issue(user)


@router.get("/me", response_model=UserPublic)
def me(user: Dict[str, Any] = Depends(get_current_user)):
    return to_public(user)


@router.get("/users", response_model=List[UserPublic])
def list_users(_: Dict[str, Any] = Depends(require_role(Role.ADMIN))):
    return [to_public(u) for u in repo.users.list_all()]


@router.patch("/users/{user_id}/role", response_model=UserPublic)
def change_role(user_id: str, role: Role, admin: Dict[str, Any] = Depends(require_role(Role.ADMIN))):
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role. Ask another administrator.",
        )
    if not repo.users.set_role(user_id, role.value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    repo.audit_log.record(admin["id"], admin["full_name"], "ROLE_CHANGED", user_id, "to=%s" % role.value)
    return to_public(repo.users.by_id(user_id))


@router.patch("/users/{user_id}/active", response_model=UserPublic)
def set_active(user_id: str, active: bool, admin: Dict[str, Any] = Depends(require_role(Role.ADMIN))):
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    if not repo.users.set_active(user_id, active):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    repo.audit_log.record(admin["id"], admin["full_name"], "USER_ACTIVE_CHANGED", user_id, "active=%s" % active)
    return to_public(repo.users.by_id(user_id))
