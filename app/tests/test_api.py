from datetime import timedelta

from app.tests.conftest import next_weekday, unique_email


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_openapi_schema_renders(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "Patient" in schema["components"]["schemas"]
    assert "JWT" in schema["components"]["securitySchemes"]


def test_login_with_wrong_password(client, admin_headers):
    response = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert response.status_code == 401


def test_read_current_user(client, admin_headers):
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_protected_routes_require_token(client):
    assert client.get("/api/patients/").status_code == 401
    assert client.get("/api/doctors/", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_create_patient(client, admin_headers):
    patient_data = {
        "first_name": "Alice",
        "last_name": "Johnson",
        "date_of_birth": "1985-05-15",
        "email": unique_email("alice"),
        "phone": "5551234567",
        "address": "456 Oak St",
        "insurance_provider": "Aetna",
        "insurance_id": "AE789012"
    }

    response = client.post("/api/patients/", json=patient_data, headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == patient_data["first_name"]
    assert data["last_name"] == patient_data["last_name"]
    assert data["email"] == patient_data["email"]

    duplicate = client.post("/api/patients/", json=patient_data, headers=admin_headers)
    assert duplicate.status_code == 400


def test_patient_crud_endpoints(client, admin_headers, create_patient):
    patient = create_patient(last_name="Searchable")

    response = client.get(f"/api/patients/{patient['id']}", headers=admin_headers)
    assert response.status_code == 200

    response = client.get("/api/patients/search", params={"query": "Searchab"}, headers=admin_headers)
    assert response.status_code == 200
    assert patient["id"] in [p["id"] for p in response.json()]

    response = client.put(f"/api/patients/{patient['id']}", json={"phone": "5550001111"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["phone"] == "5550001111"

    response = client.delete(f"/api/patients/{patient['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == patient["id"]

    assert client.get(f"/api/patients/{patient['id']}", headers=admin_headers).status_code == 404


def test_create_doctor(client, admin_headers):
    doctor_data = {
        "first_name": "Robert",
        "last_name": "Williams",
        "email": unique_email("robert"),
        "phone": "5559876543",
        "specialization": "Neurology"
    }

    response = client.post("/api/doctors/", json=doctor_data, headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == doctor_data["first_name"]
    assert data["last_name"] == doctor_data["last_name"]
    assert data["specialization"] == doctor_data["specialization"]

    response = client.get("/api/doctors/specialization/neurology", headers=admin_headers)
    assert data["id"] in [d["id"] for d in response.json()]


def test_doctor_availability_endpoints(client, admin_headers, create_doctor):
    doctor = create_doctor()

    response = client.get(f"/api/doctors/{doctor['id']}", headers=admin_headers)
    assert response.status_code == 200
    availabilities = response.json()["availabilities"]
    assert len(availabilities) == 1

    invalid = client.post(
        f"/api/doctors/{doctor['id']}/availability",
        json={"day_of_week": 2, "start_time": "17:00:00", "end_time": "09:00:00"},
        headers=admin_headers,
    )
    assert invalid.status_code == 422

    response = client.delete(
        f"/api/doctors/{doctor['id']}/availability/{availabilities[0]['id']}", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["availabilities"] == []

    response = client.delete(f"/api/doctors/{doctor['id']}", headers=admin_headers)
    assert response.status_code == 200


def test_appointment_lifecycle(client, admin_headers, create_patient, create_doctor, appointment_payload):
    patient = create_patient()
    doctor = create_doctor()
    payload = appointment_payload(patient["id"], doctor["id"])

    response = client.post("/api/appointments/", json=payload, headers=admin_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["patient_id"] == payload["patient_id"]
    assert data["doctor_id"] == payload["doctor_id"]
    assert data["status"] == payload["status"]
    appointment_id = data["id"]

    # Overlapping booking for the same doctor is rejected
    overlap = appointment_payload(patient["id"], doctor["id"], hour=10, minute=15)
    response = client.post("/api/appointments/", json=overlap, headers=admin_headers)
    assert response.status_code == 400
    assert "conflict" in response.json()["detail"]

    # Outside the doctor's working hours
    late = appointment_payload(patient["id"], doctor["id"], hour=18)
    assert client.post("/api/appointments/", json=late, headers=admin_headers).status_code == 400

    # end_time before start_time
    backwards = {**payload, "end_time": payload["start_time"]}
    assert client.post("/api/appointments/", json=backwards, headers=admin_headers).status_code == 422

    response = client.get(f"/api/appointments/{appointment_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["doctor_name"] == "Jane Smith"

    # Reschedule by moving only the start time back 30 minutes
    new_start = next_weekday(1).replace(hour=9, minute=30)
    response = client.put(
        f"/api/appointments/{appointment_id}",
        json={"start_time": new_start.isoformat(), "notes": "Moved earlier"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["notes"] == "Moved earlier"

    response = client.put(
        f"/api/appointments/{appointment_id}/status", params={"status": "confirmed"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    response = client.delete(f"/api/appointments/{appointment_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == appointment_id
    assert client.get(f"/api/appointments/{appointment_id}", headers=admin_headers).status_code == 404


def test_appointment_with_timezone_offset(client, admin_headers, create_patient, create_doctor):
    patient = create_patient()
    doctor = create_doctor()
    # 13:00+03:00 is 10:00 UTC, inside the doctor's 09:00-17:00 UTC window
    start = next_weekday(1).replace(hour=13)
    payload = {
        "patient_id": patient["id"],
        "doctor_id": doctor["id"],
        "start_time": start.isoformat() + "+03:00",
        "end_time": (start + timedelta(minutes=30)).isoformat() + "+03:00",
    }

    response = client.post("/api/appointments/", json=payload, headers=admin_headers)
    assert response.status_code == 200, response.text

    response = client.get(
        f"/api/appointments/doctor/{doctor['id']}/available-slots",
        params={"date": next_weekday(1).isoformat()},
        headers=admin_headers,
    )
    starts = [slot["start_time"] for slot in response.json()]
    assert next_weekday(1).replace(hour=10).isoformat() not in starts


def test_get_appointments(client, admin_headers, create_patient, create_doctor, appointment_payload):
    patient = create_patient()
    doctor = create_doctor()
    client.post("/api/appointments/", json=appointment_payload(patient["id"], doctor["id"]), headers=admin_headers)

    response = client.get("/api/appointments/", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert {"patient_name", "doctor_name", "doctor_specialization"} <= data[0].keys()


def test_get_doctor_available_slots(client, admin_headers, create_doctor):
    doctor = create_doctor()

    response = client.get(
        f"/api/appointments/doctor/{doctor['id']}/available-slots",
        params={"date": next_weekday(1).isoformat()},
        headers=admin_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 16
    for slot in data:
        assert "start_time" in slot
        assert "end_time" in slot
        assert "is_available" in slot

    missing = client.get(
        "/api/appointments/doctor/999999/available-slots",
        params={"date": next_weekday(1).isoformat()},
        headers=admin_headers,
    )
    assert missing.status_code == 404
