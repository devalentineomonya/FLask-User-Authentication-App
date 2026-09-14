from app.schemas.user import UserRole
from app.tests.conftest import PASSWORD, unique_email


def _login(client, email: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_public_registration_is_limited_to_patients(client):
    email = unique_email("register")
    base = {"email": email, "username": email.split("@")[0], "password": PASSWORD}

    response = client.post("/api/auth/register", json={**base, "role": "admin"})
    assert response.status_code == 403

    response = client.post("/api/auth/register", json={**base, "reference_id": 1})
    assert response.status_code == 403

    response = client.post("/api/auth/register", json=base)
    assert response.status_code == 201
    assert response.json()["role"] == "patient"

    response = client.post("/api/auth/register", json=base)
    assert response.status_code == 400


def test_admin_can_register_other_roles(client, admin_headers, create_doctor):
    doctor = create_doctor()
    email = unique_email("doctor.account")
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0],
            "password": PASSWORD,
            "role": "doctor",
            "reference_id": doctor["id"],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["reference_id"] == doctor["id"]


def test_short_password_is_rejected(client):
    email = unique_email("short")
    response = client.post(
        "/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": "short"},
    )
    assert response.status_code == 422


def test_patient_self_service_profile(client, create_patient):
    email = unique_email("self")
    client.post("/api/auth/register", json={"email": email, "username": email.split("@")[0], "password": PASSWORD})
    headers = _login(client, email)

    assert client.get("/api/patients/me", headers=headers).status_code == 404

    profile = {
        "first_name": "Self",
        "last_name": "Service",
        "date_of_birth": "1995-02-03",
        "phone": "5551112222",
        "address": "1 Self St",
    }
    response = client.post("/api/patients/", json={**profile, "email": unique_email("other")}, headers=headers)
    assert response.status_code == 400

    response = client.post("/api/patients/", json={**profile, "email": email}, headers=headers)
    assert response.status_code == 200, response.text
    patient_id = response.json()["id"]

    response = client.get("/api/patients/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == patient_id

    assert client.get(f"/api/patients/{patient_id}", headers=headers).status_code == 200
    assert client.put(f"/api/patients/{patient_id}", json={"phone": "5559999999"}, headers=headers).status_code == 200

    other = create_patient()
    assert client.get(f"/api/patients/{other['id']}", headers=headers).status_code == 403
    assert client.put(f"/api/patients/{other['id']}", json={"phone": "1"}, headers=headers).status_code == 403
    assert client.get("/api/patients/", headers=headers).status_code == 403
    assert client.delete(f"/api/patients/{patient_id}", headers=headers).status_code == 403
    assert client.post("/api/patients/", json={**profile, "email": email}, headers=headers).status_code == 400


def test_patient_appointment_permissions(client, make_user, admin_headers, create_patient, create_doctor, appointment_payload):
    patient = create_patient()
    other_patient = create_patient()
    doctor = create_doctor()
    headers = make_user(UserRole.PATIENT, reference_id=patient["id"])

    # Cannot book for someone else
    response = client.post(
        "/api/appointments/", json=appointment_payload(other_patient["id"], doctor["id"]), headers=headers
    )
    assert response.status_code == 403

    # Books for self; requested status is forced to scheduled
    payload = {**appointment_payload(patient["id"], doctor["id"], hour=11), "status": "completed"}
    response = client.post("/api/appointments/", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "scheduled"
    own_id = response.json()["id"]

    other = client.post(
        "/api/appointments/", json=appointment_payload(other_patient["id"], doctor["id"], hour=12), headers=admin_headers
    ).json()

    listed = client.get("/api/appointments/", headers=headers).json()
    assert [a["id"] for a in listed] == [own_id]

    assert client.get(f"/api/appointments/{other['id']}", headers=headers).status_code == 403
    assert client.delete(f"/api/appointments/{other['id']}", headers=headers).status_code == 403

    response = client.put(f"/api/appointments/{own_id}/status", params={"status": "confirmed"}, headers=headers)
    assert response.status_code == 403
    response = client.put(f"/api/appointments/{own_id}/status", params={"status": "cancelled"}, headers=headers)
    assert response.status_code == 200


def test_unlinked_patient_cannot_list_appointments(client, make_user):
    headers = make_user(UserRole.PATIENT)
    assert client.get("/api/appointments/", headers=headers).status_code == 403


def test_doctor_permissions(client, make_user, admin_headers, create_patient, create_doctor, appointment_payload):
    patient = create_patient()
    doctor = create_doctor()
    other_doctor = create_doctor()
    headers = make_user(UserRole.DOCTOR, reference_id=doctor["id"])

    own = client.post(
        "/api/appointments/", json=appointment_payload(patient["id"], doctor["id"], hour=13), headers=admin_headers
    ).json()
    client.post(
        "/api/appointments/", json=appointment_payload(patient["id"], other_doctor["id"], hour=14), headers=admin_headers
    )

    listed = client.get("/api/appointments/", headers=headers).json()
    assert [a["id"] for a in listed] == [own["id"]]

    assert client.put(f"/api/appointments/{own['id']}/status", params={"status": "completed"}, headers=headers).status_code == 200
    assert client.delete(f"/api/appointments/{own['id']}", headers=headers).status_code == 403

    assert client.put(f"/api/doctors/{doctor['id']}", json={"phone": "5551234000"}, headers=headers).status_code == 200
    assert client.put(f"/api/doctors/{other_doctor['id']}", json={"phone": "1"}, headers=headers).status_code == 403
    assert client.post("/api/doctors/", json={}, headers=headers).status_code in (403, 422)
    assert client.get("/api/patients/", headers=headers).status_code == 200

    # Doctors with appointments cannot be deleted
    assert client.delete(f"/api/doctors/{doctor['id']}", headers=admin_headers).status_code == 409


def test_medical_record_permissions(client, make_user, create_patient):
    patient = create_patient()
    other_patient = create_patient()
    doctor_headers = make_user(UserRole.DOCTOR)
    staff_headers = make_user(UserRole.STAFF)
    patient_headers = make_user(UserRole.PATIENT, reference_id=patient["id"])

    record_in = {"patient_id": patient["id"], "diagnosis": "Hypertension", "prescription": "Lisinopril"}

    assert client.post("/api/medical-records/", json=record_in, headers=staff_headers).status_code == 403
    assert client.post("/api/medical-records/", json=record_in, headers=patient_headers).status_code == 403

    response = client.post("/api/medical-records/", json=record_in, headers=doctor_headers)
    assert response.status_code == 200, response.text
    record_id = response.json()["id"]

    response = client.put(f"/api/medical-records/{record_id}", json={"notes": "Follow up in 3 months"}, headers=doctor_headers)
    assert response.status_code == 200
    assert response.json()["notes"] == "Follow up in 3 months"

    response = client.get(f"/api/medical-records/patient/{patient['id']}", headers=patient_headers)
    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [record_id]
    assert client.get(f"/api/medical-records/{record_id}", headers=patient_headers).status_code == 200

    assert client.get(f"/api/medical-records/patient/{other_patient['id']}", headers=patient_headers).status_code == 403
    assert client.get(f"/api/medical-records/{record_id}", headers=staff_headers).status_code == 403
    assert client.get(f"/api/medical-records/patient/{patient['id']}", headers=staff_headers).status_code == 403

    # Patients with medical records cannot be deleted
    admin_headers = make_user(UserRole.ADMIN)
    assert client.delete(f"/api/patients/{patient['id']}", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/medical-records/{record_id}", headers=doctor_headers).status_code == 403
    assert client.delete(f"/api/medical-records/{record_id}", headers=admin_headers).status_code == 200


def test_user_management_is_admin_only(client, make_user, admin_headers):
    staff_headers = make_user(UserRole.STAFF)
    assert client.get("/api/users/", headers=staff_headers).status_code == 403

    email = unique_email("managed")
    created = client.post(
        "/api/auth/register", json={"email": email, "username": email.split("@")[0], "password": PASSWORD}
    ).json()

    response = client.put(f"/api/users/{created['id']}", json={"is_active": False}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 400
