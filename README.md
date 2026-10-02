# HR ERP

[![CI](https://github.com/shubhampandey1000/hr-erp/actions/workflows/ci.yml/badge.svg)](https://github.com/shubhampandey1000/hr-erp/actions/workflows/ci.yml)

A multi-tenant HR management system built with FastAPI and PostgreSQL, covering employee management, attendance, leave tracking, and payroll — including async background job processing for payroll runs and payslip generation.

Built as a production-style engineering project: full test coverage, CI/CD, Docker containerization, and background task processing with Redis/RQ.

## Features

- **Employee management** — CRUD, role-based access control (admin / HR / manager / employee), manager hierarchies, department assignment
- **Attendance tracking** — clock-in/clock-out, comp-off requests and approvals
- **Leave management** — leave types, balances, requests, and approval workflows, with overlap and balance validation
- **Payroll** — salary structures, monthly payroll processing with attendance/leave-aware proration, a status workflow (draft → processed → paid) with immutability once paid, and PDF payslip generation
- **Background jobs** — payroll processing and payslip generation run as async jobs via Redis/RQ, with job-status polling instead of blocking HTTP requests
- **Multi-tenancy** — full organization-level data isolation across every table and service, audited and test-covered
- **Authentication** — JWT-based auth with bcrypt password hashing

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| Database | PostgreSQL (SQLite for tests) |
| ORM / Migrations | SQLAlchemy, Alembic |
| Background jobs | Redis, RQ |
| PDF generation | ReportLab |
| Testing | pytest |
| Linting | ruff |
| CI/CD | GitHub Actions |
| Containerization | Docker, Docker Compose |

## Architecture

The app runs as three cooperating services, orchestrated via Docker Compose:

- **`api`** — the FastAPI application serving HTTP requests
- **`worker`** — an RQ worker process (same codebase/image as `api`) that executes background jobs (payroll processing, payslip PDF generation)
- **`db`** / **`redis`** — PostgreSQL for persistent data, Redis as the job queue backing RQ

Payroll processing and payslip generation are enqueued by the API, executed asynchronously by the worker (each job opens its own DB session), and polled via a job-status endpoint — the API never blocks on long-running work.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- (For local, non-Docker development) Python 3.12+ and a running PostgreSQL + Redis instance

### Run with Docker (recommended)

```bash
git clone https://github.com/shubhampandey1000/hr-erp.git
cd hr-erp
cp .env.example .env   # edit values as needed
docker compose up -d --build
```

This starts four containers: `api` (port 8000), `worker`, `db` (Postgres, port 5432), and `redis` (port 6379). Database migrations run automatically on startup.

Once running, the API is live at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

### Run locally (without Docker)

```bash
python -m venv env
source env/bin/activate   # on Windows: env\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # point DATABASE_URL / REDIS_URL at your local services
alembic upgrade head
uvicorn app.main:app --reload
```

You'll also need a Redis instance reachable at the URL in `.env`, and a separate `rq worker --url <REDIS_URL>` process running if you want background jobs (payroll processing, payslip generation) to actually execute.

### Environment variables

See `.env.example` for the full list. At minimum:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret |
| `ALGORITHM` | JWT algorithm (e.g. `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |
| `REDIS_URL` | Redis connection string for the job queue |

## Running Tests

```bash
pytest -v
```

The suite runs against an in-memory SQLite database and doesn't require Docker, Postgres, or Redis for most tests — job logic is tested by calling job functions directly rather than through a live queue. A small number of tests do require a reachable Redis (matching what CI spins up as a service container).

Lint:

```bash
ruff check .
```

## API Documentation

Interactive Swagger UI is available at `/docs` once the app is running (e.g. `http://localhost:8000/docs`).

## Project Structure

```
app/
├── api/              # FastAPI routers
├── core/             # config, database, security, queue setup
├── jobs/             # RQ background job functions
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic request/response schemas
└── services/         # business logic
alembic/              # database migrations
tests/                # pytest suite
```

## License

MIT — see [LICENSE](LICENSE).
