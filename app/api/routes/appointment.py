from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import forbidden, get_current_user, is_role
from app.core.notifications import build_appointment_message, publish_notification
from app.core.timeutils import to_utc_naive
from app.crud.crud_appointment import appointment
from app.crud.crud_doctor import doctor
from app.crud.crud_patient import patient
from app.db.models import User
from app.schemas.appointment import Appointment, AppointmentCreate, AppointmentUpdate, AppointmentDetail, AppointmentStatus
from app.schemas.user import UserRole
from app.db.session import get_db

router = APIRouter()


def _linked_profile_id(current_user: User) -> int:
    if current_user.reference_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"This {current_user.role} account is not linked to a profile",
        )
    return current_user.reference_id


def _ensure_can_access(current_user: User, patient_id: int, doctor_id: int) -> None:
    if is_role(current_user, UserRole.PATIENT) and _linked_profile_id(current_user) != patient_id:
        raise forbidden()
    if is_role(current_user, UserRole.DOCTOR) and _linked_profile_id(current_user) != doctor_id:
        raise forbidden()


def _ensure_status_allowed(current_user: User, new_status: Optional[AppointmentStatus]) -> None:
    # Patients may cancel their appointments but not confirm or complete them
    if new_status is not None and is_role(current_user, UserRole.PATIENT) and new_status != AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Patients can only cancel appointments",
        )


def _ensure_slot_bookable(
    db: Session, *, doctor_id: int, start_time: datetime, end_time: datetime,
    appointment_id: Optional[int] = None
) -> None:
    if not doctor.check_availability(db, doctor_id=doctor_id, start_time=start_time, end_time=end_time):
        raise HTTPException(
            status_code=400,
            detail="Doctor is not available at the requested time"
        )

    if appointment.check_conflicts(
        db, doctor_id=doctor_id, start_time=start_time, end_time=end_time,
        appointment_id=appointment_id
    ):
        raise HTTPException(
            status_code=400,
            detail="There is a scheduling conflict with another appointment"
        )


@router.get("/", response_model=List[AppointmentDetail])
def read_appointments(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Retrieve appointments with optional date filtering.

    Patients and doctors only see their own appointments; staff and admins see all.
    """
    start_date = to_utc_naive(start_date)
    end_date = to_utc_naive(end_date)

    if is_role(current_user, UserRole.PATIENT):
        return appointment.get_by_patient(
            db, patient_id=_linked_profile_id(current_user),
            start_date=start_date, end_date=end_date, skip=skip, limit=limit
        )
    if is_role(current_user, UserRole.DOCTOR):
        return appointment.get_by_doctor(
            db, doctor_id=_linked_profile_id(current_user),
            start_date=start_date, end_date=end_date, skip=skip, limit=limit
        )
    return appointment.get_multi_with_details(
        db, start_date=start_date, end_date=end_date, skip=skip, limit=limit
    )


@router.post("/", response_model=Appointment)
def create_appointment(
    *,
    db: Session = Depends(get_db),
    appointment_in: AppointmentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new appointment. Patients book for themselves, doctors for their own
    schedule; staff and admins can book for anyone.
    """
    _ensure_can_access(current_user, appointment_in.patient_id, appointment_in.doctor_id)
    if is_role(current_user, UserRole.PATIENT):
        appointment_in.status = AppointmentStatus.SCHEDULED

    if not patient.get(db, id=appointment_in.patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    if not doctor.get(db, id=appointment_in.doctor_id):
        raise HTTPException(status_code=404, detail="Doctor not found")

    _ensure_slot_bookable(
        db,
        doctor_id=appointment_in.doctor_id,
        start_time=appointment_in.start_time,
        end_time=appointment_in.end_time,
    )

    appointment_obj = appointment.create(db, obj_in=appointment_in)

    background_tasks.add_task(
        publish_notification,
        build_appointment_message(db, appointment_obj.id, "created"),
    )

    return appointment_obj


@router.get("/doctor/{doctor_id}/available-slots", response_model=List[dict])
def get_available_slots(
    *,
    db: Session = Depends(get_db),
    doctor_id: int,
    date: datetime = Query(...),
) -> Any:
    """
    Get available 30-minute appointment slots (UTC) for a doctor on a specific date.
    """
    if not doctor.get(db, id=doctor_id):
        raise HTTPException(status_code=404, detail="Doctor not found")

    return doctor.get_available_slots(db, doctor_id=doctor_id, date=date)


@router.get("/{id}", response_model=AppointmentDetail)
def read_appointment(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get appointment by ID.
    """
    appointment_obj = appointment.get_with_details(db, id=id)
    if not appointment_obj:
        raise HTTPException(status_code=404, detail="Appointment not found")

    _ensure_can_access(current_user, appointment_obj["patient_id"], appointment_obj["doctor_id"])

    return appointment_obj


@router.put("/{id}", response_model=Appointment)
def update_appointment(
    *,
    db: Session = Depends(get_db),
    id: int,
    appointment_in: AppointmentUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update an appointment.
    """
    appointment_obj = appointment.get(db, id=id)
    if not appointment_obj:
        raise HTTPException(status_code=404, detail="Appointment not found")

    _ensure_can_access(current_user, appointment_obj.patient_id, appointment_obj.doctor_id)
    _ensure_status_allowed(current_user, appointment_in.status)

    # If rescheduling, validate the resulting time range against availability and conflicts
    if appointment_in.start_time or appointment_in.end_time:
        start_time = appointment_in.start_time or to_utc_naive(appointment_obj.start_time)
        end_time = appointment_in.end_time or to_utc_naive(appointment_obj.end_time)
        if end_time <= start_time:
            raise HTTPException(status_code=422, detail="end_time must be after start_time")

        _ensure_slot_bookable(
            db,
            doctor_id=appointment_obj.doctor_id,
            start_time=start_time,
            end_time=end_time,
            appointment_id=id,
        )

    appointment_obj = appointment.update(db, db_obj=appointment_obj, obj_in=appointment_in)

    background_tasks.add_task(
        publish_notification,
        build_appointment_message(db, appointment_obj.id, "updated"),
    )

    return appointment_obj


@router.delete("/{id}", response_model=Appointment)
def delete_appointment(
    *,
    db: Session = Depends(get_db),
    id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete an appointment (the patient, staff or admins).
    """
    if is_role(current_user, UserRole.DOCTOR):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Doctors should cancel appointments via the status endpoint",
        )

    appointment_obj = appointment.get(db, id=id)
    if not appointment_obj:
        raise HTTPException(status_code=404, detail="Appointment not found")

    _ensure_can_access(current_user, appointment_obj.patient_id, appointment_obj.doctor_id)

    # Capture details before deletion for the response and the notification
    result = Appointment.model_validate(appointment_obj)
    message = build_appointment_message(db, id, "cancelled")

    appointment.remove(db, id=id)

    background_tasks.add_task(publish_notification, message)

    return result


@router.put("/{id}/status", response_model=Appointment)
def update_appointment_status(
    *,
    db: Session = Depends(get_db),
    id: int,
    status: AppointmentStatus,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update appointment status (passed as the `status` query parameter).
    """
    appointment_obj = appointment.get(db, id=id)
    if not appointment_obj:
        raise HTTPException(status_code=404, detail="Appointment not found")

    _ensure_can_access(current_user, appointment_obj.patient_id, appointment_obj.doctor_id)
    _ensure_status_allowed(current_user, status)

    appointment_obj = appointment.update_status(db, id=id, status=status)

    background_tasks.add_task(
        publish_notification,
        build_appointment_message(db, id, "status_updated", status=status.value),
    )

    return appointment_obj
