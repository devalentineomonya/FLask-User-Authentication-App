from datetime import date, time, timedelta
from sqlalchemy.orm import Session

from app.schemas.patient import PatientCreate
from app.schemas.doctor import DoctorCreate, AvailabilityCreate
from app.schemas.appointment import AppointmentCreate, AppointmentStatus
from app.schemas.user import UserCreate, UserRole
from app.crud.crud_patient import patient
from app.crud.crud_doctor import doctor
from app.crud.crud_appointment import appointment
from app.crud.crud_user import user
from app.tests.conftest import next_weekday, unique_email


def _patient(db: Session, **overrides):
    return patient.create(db, obj_in=PatientCreate(**{
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": date(1990, 1, 1),
        "email": unique_email("crud.patient"),
        "phone": "1234567890",
        "address": "123 Test St",
        "insurance_provider": "Test Insurance",
        "insurance_id": "TI123456",
        **overrides,
    }))


def _doctor_with_tuesday_availability(db: Session):
    doctor_obj = doctor.create(db, obj_in=DoctorCreate(
        first_name="Test",
        last_name="Doctor",
        email=unique_email("crud.doctor"),
        phone="0987654321",
        specialization="Test Specialty"
    ))
    doctor.add_availability(db, doctor_id=doctor_obj.id, availability=AvailabilityCreate(
        day_of_week=1, start_time=time(9, 0), end_time=time(17, 0), is_available=True
    ))
    return doctor_obj


def test_create_patient(db: Session):
    patient_obj = _patient(db, first_name="Alice")

    assert patient_obj.id is not None
    assert patient_obj.first_name == "Alice"
    assert patient_obj.date_of_birth == date(1990, 1, 1)


def test_update_patient(db: Session):
    patient_obj = _patient(db)

    updated = patient.update(db, db_obj=patient_obj, obj_in={"phone": "5550000000"})

    assert updated.phone == "5550000000"
    assert updated.first_name == "Test"


def test_search_patients(db: Session):
    patient_obj = _patient(db, last_name="Zyxwvut")

    results = patient.search(db, query="zyxw")

    assert [p.id for p in results] == [patient_obj.id]


def test_doctor_availability(db: Session):
    doctor_obj = _doctor_with_tuesday_availability(db)
    doctor_obj = doctor.get_with_availability(db, id=doctor_obj.id)

    assert len(doctor_obj.availabilities) == 1
    assert doctor_obj.availabilities[0].day_of_week == 1
    assert doctor_obj.availabilities[0].start_time == time(9, 0)
    assert doctor_obj.availabilities[0].end_time == time(17, 0)

    tuesday = next_weekday(1)
    assert doctor.check_availability(
        db, doctor_id=doctor_obj.id,
        start_time=tuesday.replace(hour=9), end_time=tuesday.replace(hour=9, minute=30)
    )
    assert not doctor.check_availability(
        db, doctor_id=doctor_obj.id,
        start_time=tuesday.replace(hour=16, minute=45), end_time=tuesday.replace(hour=17, minute=15)
    )
    assert not doctor.check_availability(
        db, doctor_id=doctor_obj.id,
        start_time=tuesday.replace(hour=10) + timedelta(days=1),
        end_time=tuesday.replace(hour=10, minute=30) + timedelta(days=1)
    )


def test_create_appointment_and_conflicts(db: Session):
    patient_obj = _patient(db)
    doctor_obj = _doctor_with_tuesday_availability(db)

    tuesday = next_weekday(1)
    appointment_obj = appointment.create(db, obj_in=AppointmentCreate(
        patient_id=patient_obj.id,
        doctor_id=doctor_obj.id,
        start_time=tuesday.replace(hour=10),
        end_time=tuesday.replace(hour=10, minute=30),
        status=AppointmentStatus.SCHEDULED,
        notes="Test appointment"
    ))

    assert appointment_obj.id is not None
    assert appointment_obj.status == AppointmentStatus.SCHEDULED.value

    def conflicts(start_hour, start_minute, end_hour, end_minute, exclude=None):
        return appointment.check_conflicts(
            db, doctor_id=doctor_obj.id,
            start_time=tuesday.replace(hour=start_hour, minute=start_minute),
            end_time=tuesday.replace(hour=end_hour, minute=end_minute),
            appointment_id=exclude,
        )

    assert conflicts(10, 15, 10, 45)
    assert conflicts(9, 45, 10, 15)
    assert conflicts(9, 0, 11, 0)
    assert not conflicts(10, 30, 11, 0)
    assert not conflicts(9, 30, 10, 0)
    assert not conflicts(10, 0, 10, 30, exclude=appointment_obj.id)

    slots = doctor.get_available_slots(db, doctor_id=doctor_obj.id, date=tuesday)
    slot_starts = {slot["start_time"] for slot in slots}
    assert len(slots) == 15
    assert tuesday.replace(hour=10).isoformat() not in slot_starts
    assert tuesday.replace(hour=10, minute=30).isoformat() in slot_starts

    appointment.update_status(db, id=appointment_obj.id, status=AppointmentStatus.CANCELLED)
    assert not conflicts(10, 0, 10, 30)
    assert len(doctor.get_available_slots(db, doctor_id=doctor_obj.id, date=tuesday)) == 16

    details = appointment.get_with_details(db, id=appointment_obj.id)
    assert details["patient_name"] == "Test Patient"
    assert details["patient_email"] == patient_obj.email
    assert details["doctor_specialization"] == "Test Specialty"


def test_user_authentication(db: Session):
    email = unique_email("crud.user")
    user_in = UserCreate(
        email=email,
        username=email.split("@")[0],
        password="password123",
        role=UserRole.ADMIN
    )

    user_obj = user.create(db, obj_in=user_in)

    assert user_obj.id is not None
    assert user_obj.email == user_in.email
    assert user_obj.username == user_in.username
    assert user_obj.role == "admin"
    assert user_obj.hashed_password != "password123"

    authenticated_user = user.authenticate(db, email=email, password="password123")
    assert authenticated_user is not None
    assert authenticated_user.id == user_obj.id

    assert user.authenticate(db, email=email, password="wrongpassword") is None
    assert user.authenticate(db, email="missing@example.com", password="password123") is None
