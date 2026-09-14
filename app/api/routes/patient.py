from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import forbidden, get_current_admin_or_staff, get_current_staff, get_current_user, is_role
from app.crud.crud_patient import patient
from app.crud.crud_user import user
from app.db.models import Appointment, MedicalRecord, User
from app.schemas.patient import Patient, PatientCreate, PatientUpdate
from app.schemas.user import UserRole
from app.db.session import get_db

router = APIRouter()


def _ensure_can_access_patient(current_user: User, patient_id: int) -> None:
    if is_role(current_user, UserRole.PATIENT) and current_user.reference_id != patient_id:
        raise forbidden()


@router.get("/", response_model=List[Patient])
def read_patients(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_staff),
) -> Any:
    """
    Retrieve patients (staff, doctors and admins).
    """
    return patient.get_multi(db, skip=skip, limit=limit)


@router.post("/", response_model=Patient)
def create_patient(
    *,
    db: Session = Depends(get_db),
    patient_in: PatientCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new patient.

    Staff and admins can create any patient. A patient account without a linked
    profile can create its own profile, using the account's email address.
    """
    is_self_registration = is_role(current_user, UserRole.PATIENT)
    if is_self_registration:
        if current_user.reference_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account already has a patient profile.",
            )
        if patient_in.email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The patient profile email must match the account email.",
            )
    elif not is_role(current_user, UserRole.ADMIN, UserRole.STAFF):
        raise forbidden()

    if patient.get_by_email(db, email=patient_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The patient with this email already exists in the system.",
        )

    try:
        patient_obj = patient.create(db, obj_in=patient_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The patient with this email already exists in the system."
        )

    if is_self_registration:
        user.update(db, db_obj=current_user, obj_in={"reference_id": patient_obj.id})

    return patient_obj


@router.get("/me", response_model=Patient)
def read_patient_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get the patient profile linked to the current account.
    """
    if not is_role(current_user, UserRole.PATIENT) or current_user.reference_id is None:
        raise HTTPException(status_code=404, detail="No patient profile linked to this account")
    patient_obj = patient.get(db, id=current_user.reference_id)
    if not patient_obj:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient_obj


@router.get("/search", response_model=List[Patient])
def search_patients(
    *,
    db: Session = Depends(get_db),
    query: str = Query(..., min_length=3),
    current_user: User = Depends(get_current_staff),
) -> Any:
    """
    Search for patients by name or email (staff, doctors and admins).
    """
    return patient.search(db, query=query)


@router.get("/{id}", response_model=Patient)
def read_patient(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get patient by ID.
    """
    _ensure_can_access_patient(current_user, id)
    patient_obj = patient.get(db, id=id)
    if not patient_obj:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient_obj


@router.put("/{id}", response_model=Patient)
def update_patient(
    *,
    db: Session = Depends(get_db),
    id: int,
    patient_in: PatientUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a patient (the patient themself, staff or admins).
    """
    if not is_role(current_user, UserRole.PATIENT, UserRole.STAFF, UserRole.ADMIN):
        raise forbidden()
    _ensure_can_access_patient(current_user, id)

    patient_obj = patient.get(db, id=id)
    if not patient_obj:
        raise HTTPException(status_code=404, detail="Patient not found")

    if patient_in.email and patient_in.email != patient_obj.email:
        existing_patient = patient.get_by_email(db, email=patient_in.email)
        if existing_patient and existing_patient.id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The email is already registered to another patient."
            )

    try:
        return patient.update(db, db_obj=patient_obj, obj_in=patient_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data or duplicate entry."
        )


@router.delete("/{id}", response_model=Patient)
def delete_patient(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_admin_or_staff),
) -> Any:
    """
    Delete a patient (staff and admins). Patients with appointments or medical
    records cannot be deleted.
    """
    patient_obj = patient.get(db, id=id)
    if not patient_obj:
        raise HTTPException(status_code=404, detail="Patient not found")

    has_dependencies = (
        db.query(Appointment.id).filter(Appointment.patient_id == id).first()
        or db.query(MedicalRecord.id).filter(MedicalRecord.patient_id == id).first()
    )
    if has_dependencies:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a patient with appointments or medical records."
        )

    result = Patient.model_validate(patient_obj)
    patient.remove(db, id=id)
    return result
