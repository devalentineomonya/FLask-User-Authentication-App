import os
import tempfile
import uuid
from datetime import datetime, time, timedelta, timezone

# Configure the app for testing before anything imports app.core.config.
# Environment variables take precedence over .env, so tests never touch a real database.
_tmp_dir = tempfile.mkdtemp(prefix="healthcare-tests-")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", f"sqlite:///{os.path.join(_tmp_dir, 'test.db')}"
)
os.environ["SECRET_KEY"] = "test_secret_key_for_tests_minimum_32_characters_long"
os.environ["ENVIRONMENT"] = "testing"
os.environ["CACHE_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["NOTIFICATIONS_ENABLED"] = "false"
os.environ["FIRST_ADMIN_EMAIL"] = ""
os.environ["FIRST_ADMIN_PASSWORD"] = ""

import pytest
from fastapi.testclient import TestClient

from app.crud.crud_user import user
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.schemas.user import UserCreate, UserRole

PASSWORD = "password123"


def unique_email(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@example.com"


def next_weekday(weekday: int) -> datetime:
    """Midnight (naive UTC) of the next date after today falling on `weekday`."""
    day = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return datetime.combine(day.date(), time.min)


@pytest.fixture(scope="session", autouse=True)
def test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(test_db):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def client(test_db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def make_user(client):
    """Create a user directly in the DB and return auth headers for it."""
    def _make_user(role: UserRole, reference_id: int | None = None, email: str | None = None) -> dict:
        email = email or unique_email(role.value)
        with SessionLocal() as session:
            user.create(session, obj_in=UserCreate(
                email=email,
                username=email.split("@")[0],
                password=PASSWORD,
                role=role,
                reference_id=reference_id,
            ))
        response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _make_user


@pytest.fixture(scope="session")
def admin_headers(make_user):
    return make_user(UserRole.ADMIN)


@pytest.fixture(scope="session")
def create_patient(client, admin_headers):
    def _create_patient(**overrides) -> dict:
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1990-01-01",
            "email": unique_email("patient"),
            "phone": "1234567890",
            "address": "123 Main St",
            "insurance_provider": "Blue Cross",
            "insurance_id": "BC123456",
            **overrides,
        }
        response = client.post("/api/patients/", json=data, headers=admin_headers)
        assert response.status_code == 200, response.text
        return response.json()

    return _create_patient


@pytest.fixture(scope="session")
def create_doctor(client, admin_headers):
    """Create a doctor available 09:00-17:00 UTC on Tuesdays."""
    def _create_doctor(**overrides) -> dict:
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": unique_email("doctor"),
            "phone": "0987654321",
            "specialization": "Cardiology",
            **overrides,
        }
        response = client.post("/api/doctors/", json=data, headers=admin_headers)
        assert response.status_code == 200, response.text
        doctor = response.json()

        response = client.post(
            f"/api/doctors/{doctor['id']}/availability",
            json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "17:00:00", "is_available": True},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        return doctor

    return _create_doctor


@pytest.fixture(scope="session")
def appointment_payload():
    def _payload(patient_id: int, doctor_id: int, hour: int = 10, minute: int = 0, length: int = 30) -> dict:
        start = next_weekday(1).replace(hour=hour, minute=minute)
        return {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=length)).isoformat(),
            "status": "scheduled",
            "notes": "Regular checkup",
        }

    return _payload
