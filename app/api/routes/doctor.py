from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.deps import forbidden, get_current_admin, get_current_admin_or_staff, get_current_user, is_role
from app.crud.crud_doctor import doctor
from app.db.models import Appointment, Availability as AvailabilityModel, User
from app.schemas.doctor import Doctor, DoctorCreate, DoctorUpdate, DoctorWithAvailability, AvailabilityCreate
from app.schemas.user import UserRole
from app.db.session import get_db

router = APIRouter()


def _ensure_can_manage_doctor(current_user: User, doctor_id: int) -> None:
    """Admins and staff manage every doctor; a doctor manages only their own profile."""
    if is_role(current_user, UserRole.ADMIN, UserRole.STAFF):
        return
    if is_role(current_user, UserRole.DOCTOR) and current_user.reference_id == doctor_id:
        return
    raise forbidden()


@router.get("/", response_model=List[Doctor])
def read_doctors(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> Any:
    """
    Retrieve doctors.
    """
    return doctor.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=Doctor)
def create_doctor(
    *,
    db: Session = Depends(get_db),
    doctor_in: DoctorCreate,
    current_user: User = Depends(get_current_admin_or_staff),
) -> Any:
    """
    Create new doctor (staff and admins).
    """
    existing_doctor = doctor.get_by_email(db, email=doctor_in.email)
    if existing_doctor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The doctor with this email already exists.",
        )

    try:
        doctor_obj = doctor.create(db, obj_in=doctor_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate doctor entry or invalid data."
        )
    return doctor_obj

@router.get("/specialization/{specialization}", response_model=List[Doctor])
def get_doctors_by_specialization(
    *,
    db: Session = Depends(get_db),
    specialization: str,
) -> Any:
    """
    Get doctors by specialization (case-insensitive).
    """
    return doctor.get_by_specialization(db, specialization=specialization)

@router.get("/{id}", response_model=DoctorWithAvailability)
def read_doctor(
    *,
    db: Session = Depends(get_db),
    id: int,
) -> Any:
    """
    Get doctor by ID with availability.
    """
    doctor_obj = doctor.get_with_availability(db, id=id)
    if not doctor_obj:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor_obj

@router.put("/{id}", response_model=Doctor)
def update_doctor(
    *,
    db: Session = Depends(get_db),
    id: int,
    doctor_in: DoctorUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a doctor (the doctor themself, staff or admins).
    """
    _ensure_can_manage_doctor(current_user, id)
    doctor_obj = doctor.get(db, id=id)
    if not doctor_obj:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if doctor_in.email and doctor_in.email != doctor_obj.email:
        existing_doctor = doctor.get_by_email(db, email=doctor_in.email)
        if existing_doctor and existing_doctor.id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered to another doctor."
            )

    try:
        doctor_obj = doctor.update(db, db_obj=doctor_obj, obj_in=doctor_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data or duplicate entry."
        )
    return doctor_obj

@router.delete("/{id}", response_model=Doctor)
def delete_doctor(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_admin),
) -> Any:
    """
    Delete a doctor and their availability (admins only). Doctors with
    appointments cannot be deleted.
    """
    doctor_obj = doctor.get(db, id=id)
    if not doctor_obj:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if db.query(Appointment.id).filter(Appointment.doctor_id == id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete doctor with existing appointments."
        )

    result = Doctor.model_validate(doctor_obj)
    doctor.remove(db, id=id)
    return result

@router.post("/{id}/availability", response_model=DoctorWithAvailability)
def add_doctor_availability(
    *,
    db: Session = Depends(get_db),
    id: int,
    availability_in: AvailabilityCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Add a weekly availability window for a doctor (times are UTC).
    """
    _ensure_can_manage_doctor(current_user, id)
    doctor_obj = doctor.get(db, id=id)
    if not doctor_obj:
        raise HTTPException(status_code=404, detail="Doctor not found")

    try:
        doctor_obj = doctor.add_availability(db, doctor_id=id, availability=availability_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid availability data or time conflict."
        )
    return doctor_obj

@router.delete("/{id}/availability/{availability_id}", response_model=DoctorWithAvailability)
def delete_doctor_availability(
    *,
    db: Session = Depends(get_db),
    id: int,
    availability_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Remove an availability window from a doctor.
    """
    _ensure_can_manage_doctor(current_user, id)
    availability_obj = db.get(AvailabilityModel, availability_id)
    if not availability_obj or availability_obj.doctor_id != id:
        raise HTTPException(status_code=404, detail="Availability not found")

    db.delete(availability_obj)
    db.commit()
    return doctor.get_with_availability(db, id=id)
