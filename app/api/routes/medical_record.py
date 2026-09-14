from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import forbidden, get_current_admin, get_current_doctor, get_current_user, is_role
from app.crud.crud_appointment import appointment
from app.crud.crud_medical_record import medical_record
from app.crud.crud_patient import patient
from app.db.models import User
from app.db.session import get_db
from app.schemas.medical_record import MedicalRecord, MedicalRecordCreate, MedicalRecordUpdate
from app.schemas.user import UserRole

router = APIRouter()


def _ensure_can_read_patient_records(current_user: User, patient_id: int) -> None:
    """Doctors and admins read all records; patients only their own; staff none."""
    if is_role(current_user, UserRole.DOCTOR, UserRole.ADMIN):
        return
    if is_role(current_user, UserRole.PATIENT) and current_user.reference_id == patient_id:
        return
    raise forbidden()


@router.post("/", response_model=MedicalRecord)
def create_medical_record(
    *,
    db: Session = Depends(get_db),
    record_in: MedicalRecordCreate,
    current_user: User = Depends(get_current_doctor),
) -> Any:
    """
    Create a medical record (doctors and admins).
    """
    if not patient.get(db, id=record_in.patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")

    if record_in.appointment_id is not None:
        appointment_obj = appointment.get(db, id=record_in.appointment_id)
        if not appointment_obj:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment_obj.patient_id != record_in.patient_id:
            raise HTTPException(status_code=400, detail="Appointment belongs to a different patient")

    return medical_record.create(db, obj_in=record_in)


@router.get("/patient/{patient_id}", response_model=List[MedicalRecord])
def read_patient_medical_records(
    *,
    db: Session = Depends(get_db),
    patient_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    List a patient's medical records, newest first.
    """
    _ensure_can_read_patient_records(current_user, patient_id)
    if not patient.get(db, id=patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    return medical_record.get_by_patient(db, patient_id=patient_id, skip=skip, limit=limit)


@router.get("/{id}", response_model=MedicalRecord)
def read_medical_record(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a medical record by ID.
    """
    if is_role(current_user, UserRole.STAFF):
        raise forbidden()
    record = medical_record.get(db, id=id)
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
    _ensure_can_read_patient_records(current_user, record.patient_id)
    return record


@router.put("/{id}", response_model=MedicalRecord)
def update_medical_record(
    *,
    db: Session = Depends(get_db),
    id: int,
    record_in: MedicalRecordUpdate,
    current_user: User = Depends(get_current_doctor),
) -> Any:
    """
    Update a medical record (doctors and admins).
    """
    record = medical_record.get(db, id=id)
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
    return medical_record.update(db, db_obj=record, obj_in=record_in)


@router.delete("/{id}", response_model=MedicalRecord)
def delete_medical_record(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_admin),
) -> Any:
    """
    Delete a medical record (admins only).
    """
    record = medical_record.get(db, id=id)
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
    result = MedicalRecord.model_validate(record)
    medical_record.remove(db, id=id)
    return result
