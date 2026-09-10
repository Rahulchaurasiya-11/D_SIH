"""FastAPI dependencies: authentication and role enforcement."""

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.db import repositories as repo
from app.models import ROLE_RANK, Role

_bearer = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Provide a valid bearer token.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR

    claims = decode_token(credentials.credentials)
    if not claims or not claims.get("sub"):
        raise CREDENTIALS_ERROR

    user = repo.users.by_id(claims["sub"])
    if not user:
        raise CREDENTIALS_ERROR
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )
    return user


def require_role(minimum: Role):
    """
    Guards a route by rank: ADMIN satisfies SENIOR_OFFICER, which satisfies INSPECTOR.

    Enforced server-side on every protected route. The frontend hides what a role
    cannot use, but hiding a button is not access control.
    """
    needed = ROLE_RANK[minimum.value]

    def _guard(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if ROLE_RANK.get(user.get("role", ""), 0) < needed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires %s privileges or higher." % minimum.value.replace("_", " ").title(),
            )
        return user

    return _guard


def can_view_inspection(user: Dict[str, Any], inspection: Dict[str, Any]) -> bool:
    """An inspector sees only their own inspections; senior officers and admins see all."""
    if ROLE_RANK.get(user.get("role", ""), 0) >= ROLE_RANK[Role.SENIOR_OFFICER.value]:
        return True
    return inspection.get("officer_id") == user.get("id")
