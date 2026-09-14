from app.api.routes.auth import router as auth_router
from app.api.routes.user import router as user_router
from app.api.routes.patient import router as patient_router
from app.api.routes.doctor import router as doctor_router
from app.api.routes.appointment import router as appointment_router
from app.api.routes.medical_record import router as medical_record_router

__all__ = [
    "auth_router",
    "user_router",
    "patient_router",
    "doctor_router",
    "appointment_router",
    "medical_record_router",
]
