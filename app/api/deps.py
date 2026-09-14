from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import TokenPayload, UserRole
from app.crud.crud_user import user

bearer_scheme = HTTPBearer(
    scheme_name="JWT",
    description="Paste the access_token returned by POST /api/auth/login",
    auto_error=False,
)

def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

def _user_from_token(db: Session, token: str) -> User:
    try:
        token_data = TokenPayload(**decode_access_token(token))
    except (jwt.PyJWTError, ValidationError):
        raise _credentials_exception()

    if token_data.sub is None:
        raise _credentials_exception()

    user_obj = user.get(db, id=token_data.sub)
    if not user_obj:
        raise _credentials_exception()
    if not user_obj.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return user_obj

def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise _credentials_exception()
    return _user_from_token(db, credentials.credentials)

def get_optional_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[User]:
    if credentials is None:
        return None
    return _user_from_token(db, credentials.credentials)

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

def require_roles(*roles: UserRole):
    allowed = {role.value for role in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges"
            )
        return current_user

    return dependency

get_current_admin = require_roles(UserRole.ADMIN)
get_current_doctor = require_roles(UserRole.DOCTOR, UserRole.ADMIN)
get_current_staff = require_roles(UserRole.STAFF, UserRole.ADMIN, UserRole.DOCTOR)
get_current_admin_or_staff = require_roles(UserRole.ADMIN, UserRole.STAFF)

def is_role(current_user: User, *roles: UserRole) -> bool:
    return current_user.role in {role.value for role in roles}

def forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
