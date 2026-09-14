from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.crud.crud_base import CRUDBase
from app.db.models import Appointment, Patient, Doctor
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentStatus

class CRUDAppointment(CRUDBase[Appointment, AppointmentCreate, AppointmentUpdate]):
    def _details_query(self, db: Session):
        return db.query(
            Appointment,
            Patient.first_name,
            Patient.last_name,
            Patient.email,
            Doctor.first_name,
            Doctor.last_name,
            Doctor.specialization,
        ).join(
            Patient, Appointment.patient_id == Patient.id
        ).join(
            Doctor, Appointment.doctor_id == Doctor.id
        )

    @staticmethod
    def _to_detail(row) -> Dict[str, Any]:
        (appointment, patient_first_name, patient_last_name, patient_email,
         doctor_first_name, doctor_last_name, doctor_specialization) = row
        return {
            "id": appointment.id,
            "patient_id": appointment.patient_id,
            "doctor_id": appointment.doctor_id,
            "start_time": appointment.start_time,
            "end_time": appointment.end_time,
            "status": appointment.status,
            "notes": appointment.notes,
            "created_at": appointment.created_at,
            "updated_at": appointment.updated_at,
            "patient_name": f"{patient_first_name} {patient_last_name}",
            "patient_email": patient_email,
            "doctor_name": f"{doctor_first_name} {doctor_last_name}",
            "doctor_specialization": doctor_specialization,
        }

    def get_by_patient(
        self, db: Session, *, patient_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return self.get_multi_with_details(
            db, patient_id=patient_id, start_date=start_date, end_date=end_date,
            skip=skip, limit=limit
        )

    def get_by_doctor(
        self, db: Session, *, doctor_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return self.get_multi_with_details(
            db, doctor_id=doctor_id, start_date=start_date, end_date=end_date,
            skip=skip, limit=limit
        )

    def get_with_details(self, db: Session, *, id: int) -> Optional[Dict[str, Any]]:
        row = self._details_query(db).filter(Appointment.id == id).first()
        return self._to_detail(row) if row else None

    def get_multi_with_details(
        self, db: Session, *,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        query = self._details_query(db)

        if patient_id is not None:
            query = query.filter(Appointment.patient_id == patient_id)
        if doctor_id is not None:
            query = query.filter(Appointment.doctor_id == doctor_id)
        if start_date:
            query = query.filter(Appointment.start_time >= start_date)
        if end_date:
            query = query.filter(Appointment.end_time <= end_date)

        rows = query.order_by(Appointment.start_time).offset(skip).limit(limit).all()
        return [self._to_detail(row) for row in rows]

    def check_conflicts(
        self, db: Session, *,
        doctor_id: int,
        start_time: datetime,
        end_time: datetime,
        appointment_id: Optional[int] = None
    ) -> bool:
        """
        Check if there are any conflicting appointments for the doctor.
        If appointment_id is provided, exclude that appointment from the check.
        """
        query = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status != AppointmentStatus.CANCELLED.value,
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        )

        if appointment_id is not None:
            query = query.filter(Appointment.id != appointment_id)

        return query.count() > 0

    def update_status(self, db: Session, *, id: int, status: AppointmentStatus) -> Optional[Appointment]:
        appointment = self.get(db, id=id)
        if not appointment:
            return None

        appointment.status = status.value
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        return appointment

appointment = CRUDAppointment(Appointment)
