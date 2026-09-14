from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user, is_role
from app.core.security import create_access_token
from app.crud.crud_user import user
from app.db.models import User as UserModel
from app.schemas.user import LoginRequest, User, UserCreate, UserRole, Token
from app.db.session import get_db

router = APIRouter()


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login_access_token(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Token login with JSON, get an access token for future requests.

    - **email**: Email address
    - **password**: User password
    """
    user_obj = user.authenticate(
        db, email=login_data.email, password=login_data.password
    )
    if not user_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return {
        "access_token": create_access_token(user_obj.id, user_obj.role),
        "token_type": "bearer",
    }


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: Optional[UserModel] = Depends(get_optional_current_user),
) -> Any:
    """
    Create new user.

    Anyone may register a patient account. Only admins may create accounts with
    other roles or link an account to an existing patient/doctor profile.
    """
    caller_is_admin = current_user is not None and is_role(current_user, UserRole.ADMIN)
    if not caller_is_admin and (user_in.role != UserRole.PATIENT or user_in.reference_id is not None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create non-patient accounts or set reference_id",
        )

    if user.get_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    if user.get_by_username(db, username=user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this username already exists in the system.",
        )
    return user.create(db, obj_in=user_in)


@router.get("/me", response_model=User)
def read_users_me(
    current_user: UserModel = Depends(get_current_user)
) -> Any:
    """
    Get current user.
    """
    return current_user
