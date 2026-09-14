from typing import List, Optional, Dict, Any
from datetime import datetime, time, timedelta
from sqlalchemy.orm import Session, joinedload

from app.core.timeutils import to_utc_naive
from app.crud.crud_base import CRUDBase
from app.db.models import Doctor, Availability, Appointment
from app.schemas.appointment import AppointmentStatus
from app.schemas.doctor import DoctorCreate, DoctorUpdate, AvailabilityCreate

SLOT_MINUTES = 30

class CRUDDoctor(CRUDBase[Doctor, DoctorCreate, DoctorUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[Doctor]:
        return db.query(Doctor).filter(Doctor.email == email).first()

    def get_by_specialization(self, db: Session, *, specialization: str) -> List[Doctor]:
        return db.query(Doctor).filter(Doctor.specialization.ilike(specialization)).all()

    def get_with_availability(self, db: Session, *, id: int) -> Optional[Doctor]:
        return db.query(Doctor).options(joinedload(Doctor.availabilities)).filter(Doctor.id == id).first()

    def add_availability(self, db: Session, *, doctor_id: int, availability: AvailabilityCreate) -> Doctor:
        db_availability = Availability(
            doctor_id=doctor_id,
            day_of_week=availability.day_of_week,
            start_time=availability.start_time,
            end_time=availability.end_time,
            is_available=availability.is_available
        )
        db.add(db_availability)
        db.commit()

        return self.get_with_availability(db, id=doctor_id)

    def check_availability(self, db: Session, *, doctor_id: int, start_time: datetime, end_time: datetime) -> bool:
        start_time = to_utc_naive(start_time)
        end_time = to_utc_naive(end_time)

        # Availability windows are defined per weekday and cannot span midnight
        if start_time.date() != end_time.date():
            return False

        availability = db.query(Availability).filter(
            Availability.doctor_id == doctor_id,
            Availability.day_of_week == start_time.weekday(),
            Availability.is_available.is_(True),
            Availability.start_time <= start_time.time(),
            Availability.end_time >= end_time.time()
        ).first()

        return availability is not None

    def get_available_slots(self, db: Session, *, doctor_id: int, date: datetime) -> List[Dict[str, Any]]:
        date = to_utc_naive(date)

        availabilities = db.query(Availability).filter(
            Availability.doctor_id == doctor_id,
            Availability.day_of_week == date.weekday(),
            Availability.is_available.is_(True)
        ).order_by(Availability.start_time).all()

        if not availabilities:
            return []

        start_of_day = datetime.combine(date.date(), time.min)
        end_of_day = start_of_day + timedelta(days=1)

        appointments = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.start_time < end_of_day,
            Appointment.end_time > start_of_day,
            Appointment.status != AppointmentStatus.CANCELLED.value
        ).all()
        booked = [(to_utc_naive(a.start_time), to_utc_naive(a.end_time)) for a in appointments]

        slots = []
        slot_length = timedelta(minutes=SLOT_MINUTES)
        for availability in availabilities:
            current_time = datetime.combine(date.date(), availability.start_time)
            end_time = datetime.combine(date.date(), availability.end_time)

            while current_time + slot_length <= end_time:
                slot_end_time = current_time + slot_length

                if not any(current_time < booked_end and slot_end_time > booked_start
                           for booked_start, booked_end in booked):
                    slots.append({
                        "start_time": current_time.isoformat(),
                        "end_time": slot_end_time.isoformat(),
                        "is_available": True
                    })

                current_time = slot_end_time

        return slots

doctor = CRUDDoctor(Doctor)
