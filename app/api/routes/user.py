from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.crud.crud_user import user
from app.db.session import get_db
from app.schemas.user import User, UserUpdate

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/", response_model=List[User])
def read_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> Any:
    """
    Retrieve users (admin only).
    """
    return user.get_multi(db, skip=skip, limit=limit)


@router.get("/{id}", response_model=User)
def read_user(*, db: Session = Depends(get_db), id: int) -> Any:
    """
    Get user by ID (admin only).
    """
    user_obj = user.get(db, id=id)
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    return user_obj


@router.put("/{id}", response_model=User)
def update_user(*, db: Session = Depends(get_db), id: int, user_in: UserUpdate) -> Any:
    """
    Update a user's email, role, active flag or linked profile (admin only).
    """
    user_obj = user.get(db, id=id)
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.email and user_in.email != user_obj.email:
        existing = user.get_by_email(db, email=user_in.email)
        if existing and existing.id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The email is already registered to another user.",
            )

    return user.update(db, db_obj=user_obj, obj_in=user_in)
