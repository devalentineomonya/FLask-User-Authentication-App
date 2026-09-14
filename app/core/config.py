import logging
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

DEFAULT_SECRET_KEY = "your-secret-key-for-development-only"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "Healthcare Appointment System"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/healthcare"

    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
    ]

    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 60
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    NOTIFICATIONS_ENABLED: bool = True

    # Optional bootstrap admin, created on startup if no user with this email exists
    FIRST_ADMIN_EMAIL: str | None = None
    FIRST_ADMIN_PASSWORD: str | None = None


settings = Settings()

if settings.SECRET_KEY == DEFAULT_SECRET_KEY:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    logger.warning("Using the default development SECRET_KEY; set SECRET_KEY in the environment")
