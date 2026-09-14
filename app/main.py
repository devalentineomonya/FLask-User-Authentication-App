import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
import uvicorn

from app.api.routes import (
    appointment_router,
    auth_router,
    doctor_router,
    medical_record_router,
    patient_router,
    user_router,
)
from app.core.cache import CacheMiddleware
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.crud.crud_user import user
from app.db.session import SessionLocal, engine, get_db
from app.db import models
from app.api.deps import get_current_user
from app.schemas.user import UserCreate, UserRole

logger = logging.getLogger(__name__)


def create_first_admin() -> None:
    if not (settings.FIRST_ADMIN_EMAIL and settings.FIRST_ADMIN_PASSWORD):
        return
    with SessionLocal() as db:
        if user.get_by_email(db, email=settings.FIRST_ADMIN_EMAIL):
            return
        if user.get_by_username(db, username="admin"):
            logger.error("Cannot create initial admin: username 'admin' is already taken")
            return
        user.create(db, obj_in=UserCreate(
            email=settings.FIRST_ADMIN_EMAIL,
            username="admin",
            password=settings.FIRST_ADMIN_PASSWORD,
            role=UserRole.ADMIN,
        ))
        logger.info("Created initial admin user %s", settings.FIRST_ADMIN_EMAIL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    create_first_admin()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for managing healthcare appointments",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware added last runs first: CORS, then rate limiting, then caching
if settings.CACHE_ENABLED:
    app.add_middleware(CacheMiddleware)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimiter)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = settings.API_V1_STR
authenticated = [Depends(get_current_user)]

# Authentication router has public login/register endpoints
app.include_router(auth_router, prefix=f"{api}/auth", tags=["Authentication"])
app.include_router(user_router, prefix=f"{api}/users", tags=["Users"], dependencies=authenticated)
app.include_router(patient_router, prefix=f"{api}/patients", tags=["Patients"], dependencies=authenticated)
app.include_router(doctor_router, prefix=f"{api}/doctors", tags=["Doctors"], dependencies=authenticated)
app.include_router(appointment_router, prefix=f"{api}/appointments", tags=["Appointments"], dependencies=authenticated)
app.include_router(
    medical_record_router, prefix=f"{api}/medical-records", tags=["Medical Records"], dependencies=authenticated
)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to the Healthcare Appointment System API /docs for docs"}

@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        logger.exception("Health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy: database unavailable"
        )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
