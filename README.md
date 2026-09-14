# Health Care Management System — FastAPI Backend

A modern, robust healthcare management API built with FastAPI — delivering secure, scalable, and efficient healthcare services with real-time notifications.

## 🚀 Quick Start with Docker

### Prerequisites
- **Docker** & **Docker Compose**
- **Python 3.11+** (for local development)

### Production Deployment
```bash
cp .env.example .env   # then set real passwords and SECRET_KEY
docker compose up --build -d
```

The API will be available at: [http://localhost:8000](http://localhost:8000)
API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

Set `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` in `.env` to have an admin account created on first startup.

---

## 🏗️ Tech Stack

### Backend & API
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white)

### Database & Caching
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?logo=rabbitmq&logoColor=white)

### Infrastructure & DevOps
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-000000?logo=jsonwebtokens&logoColor=white)

---

## 📁 Project Structure

```
.
├── app/
│   ├── api/
│   │   ├── routes/           # API endpoint handlers
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── patient.py
│   │   │   ├── doctor.py
│   │   │   ├── appointment.py
│   │   │   └── medical_record.py
│   │   └── deps.py           # Auth and role dependencies
│   ├── core/                 # Core application logic
│   │   ├── config.py         # Configuration management
│   │   ├── security.py       # JWT and password hashing
│   │   ├── cache.py          # Redis response caching middleware
│   │   ├── rate_limiter.py   # Redis rate limiting middleware
│   │   ├── notifications.py  # Publishes appointment events to RabbitMQ
│   │   └── timeutils.py      # UTC normalization
│   ├── crud/                 # Database operations layer
│   ├── db/                   # SQLAlchemy models and session
│   ├── schemas/              # Pydantic schemas
│   └── tests/                # Test suites
├── docker-compose.yml        # Multi-service orchestration
├── Dockerfile                # API container
├── Dockerfile.notification   # Notification worker container
├── notification_service.py   # Async notification worker (RabbitMQ → email)
├── API_EXAMPLES.http         # Example requests
└── .env.example              # Environment template
```

---

## 🐳 Docker Services

The system runs as a multi-container application. Only the API port is published; the other services are reachable on the internal network.

| Service | Purpose | Port | Health Check |
|---------|---------|------|--------------|
| **app** | FastAPI Application | 8000 | HTTP 200 on /health |
| **notification** | Email notification worker | – | Restarts on failure |
| **db** | PostgreSQL Database | 5432 (internal) | `pg_isready` |
| **redis** | Cache and rate limiting | 6379 (internal) | `redis-cli ping` |
| **rabbitmq** | Message Queue | 5672 (internal) | `rabbitmq-diagnostics ping` |

---

## 🛠️ Getting Started

### Option 1: Docker (Recommended)
```bash
# Production deployment
docker compose up --build -d

# View logs
docker compose logs -f app notification

# Stop services
docker compose down
```

### Option 2: Local Development
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.\.venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -r requirements-dev.txt

# Point the app at your services (or put these in .env)
export DATABASE_URL=postgresql://user:pass@localhost:5432/healthcare
export SECRET_KEY=dev-secret

# Run the application
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Redis and RabbitMQ are optional locally: caching and rate limiting fail open, and notifications are logged as errors
when RabbitMQ is unreachable. Disable them with `CACHE_ENABLED=false`, `RATE_LIMIT_ENABLED=false` and
`NOTIFICATIONS_ENABLED=false`.

---

## 📜 Available Commands

### Docker Commands
| Command | Description |
|---------|-------------|
| `docker compose up --build -d` | Build and start all services |
| `docker compose logs -f [service]` | Follow service logs |
| `docker compose down` | Stop and remove containers |
| `docker compose exec app [cmd]` | Execute command in app container |

### Development Commands
| Command | Description |
|---------|-------------|
| `uvicorn app.main:app --reload` | Start development server |
| `pytest -q` | Run test suite quietly |
| `pytest -v` | Run tests with verbose output |
| `pytest --cov=app` | Run tests with coverage |

---

## 🎯 Core Features

- **🔐 Secure Authentication** – JWT (HS256) bearer tokens, bcrypt password hashing
- **👥 Role-Based Access Control** – Patient, Doctor, Staff and Admin roles
- **📅 Appointment Management** – Availability windows, conflict detection, free slot lookup, rescheduling and cancellation
- **🩺 Medical Records** – Doctor-authored records, readable by the patient
- **⚡ Real-time Notifications** – Appointment events published to RabbitMQ and emailed by a worker
- **💾 Caching** – Per-user Redis response caching, invalidated on writes
- **🚀 Rate Limiting** – Per-IP request throttling
- **📊 Health Checks** – Container and service health monitoring

### API Overview

| Prefix | Endpoints |
|--------|-----------|
| `/api/auth` | `POST /login`, `POST /register`, `GET /me` |
| `/api/users` | Admin user management: list, get, update (role, active flag, linked profile) |
| `/api/patients` | CRUD, `GET /me`, `GET /search?query=` |
| `/api/doctors` | CRUD, `GET /specialization/{name}`, `POST/DELETE /{id}/availability` |
| `/api/appointments` | CRUD, `PUT /{id}/status?status=`, `GET /doctor/{id}/available-slots?date=` |
| `/api/medical-records` | CRUD, `GET /patient/{patient_id}` |

All scheduling times are **UTC**. Timestamps with an offset are converted; timestamps without one are treated as UTC.
Doctor availability is a weekly window (`day_of_week` 0 = Monday) and slots are 30 minutes.

### Roles

User accounts link to a patient or doctor profile through `reference_id`.

| Role | Access |
|------|--------|
| **Patient** | Registers publicly, creates and edits their own profile, books/reschedules/cancels their own appointments, reads their own medical records |
| **Doctor** | Reads patients, manages their own profile, availability and appointment statuses, creates and edits medical records |
| **Staff** | Manages patients, doctors and all appointments; no medical record access |
| **Admin** | Everything, including user management and creating non-patient accounts via `/api/auth/register` |

---

## 📦 Key Dependencies

- `fastapi`, `uvicorn` – Web framework and ASGI server
- `pydantic`, `pydantic-settings`, `email-validator` – Validation and settings
- `sqlalchemy`, `psycopg2-binary` – ORM and PostgreSQL driver
- `PyJWT`, `bcrypt` – Tokens and password hashing
- `redis` – Caching and rate limiting
- `aio-pika` – RabbitMQ publisher (API) and consumer (worker)
- `aiosmtplib` – Email delivery (worker)
- `pytest`, `pytest-cov`, `httpx` – Testing (`requirements-dev.txt`)

---

## ⚙️ Configuration

### Environment Variables
```bash
# Used by docker-compose.yml
DB_PASSWORD=your_secure_password
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=your_rabbitmq_password
SECRET_KEY=your_jwt_secret_key          # required when ENVIRONMENT=production

# Read by the app (compose sets these from the values above)
DATABASE_URL=postgresql://user:pass@db:5432/healthcare_db
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://user:pass@rabbitmq:5672/
ACCESS_TOKEN_EXPIRE_MINUTES=30
CACHE_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
NOTIFICATIONS_ENABLED=true
FIRST_ADMIN_EMAIL=admin@example.com
FIRST_ADMIN_PASSWORD=change-me-please

# Notification worker (leave SMTP_SERVER empty to log emails instead of sending)
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=noreply@example.com
```

### Configuration Files
- `app/core/config.py` – Centralized configuration management
- `docker-compose.yml` – Service orchestration
- `Dockerfile` – Application container definition
- `Dockerfile.notification` – Worker container definition

---

## 🚀 Deployment

### Production with Docker Compose
1. Copy `.env.example` to `.env` and set real values
2. Run `docker compose up --build -d`
3. Access API at `http://your-server:8000`
4. Monitor services with `docker compose logs -f`

Tables are created automatically on startup. There are no migrations yet, so schema changes to an existing
database must be applied manually.

### Health Checks
- API: `GET /health`
- Database, Redis, RabbitMQ: automatic health checks in compose

---

## ⚡ Performance & Security

- **Multi-stage Docker builds** for optimized image sizes
- **Non-root user execution** for enhanced security
- **Connection pooling** with pre-ping for database efficiency
- **Request rate limiting** to prevent abuse
- **JWT token expiration** for session security
- **Password length validation** (8–72 bytes) with bcrypt hashing

---

## 🧪 Testing

Tests use a throwaway SQLite database by default and never read `DATABASE_URL`.
Set `TEST_DATABASE_URL` to run them against PostgreSQL (CI does this).

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test module
pytest app/tests/test_api.py -v

# Against PostgreSQL (the database is dropped and recreated)
TEST_DATABASE_URL=postgresql://test:test@localhost:5432/test pytest
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. Commit your changes
   ```bash
   git commit -m 'Add amazing feature'
   ```
4. Push to the branch
   ```bash
   git push origin feature/amazing-feature
   ```
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**.
See the `LICENSE` file for more information.

---

### 🏥 Built with ❤️ for Modern Healthcare Management

Delivering secure, scalable healthcare APIs with cutting-edge technology.
