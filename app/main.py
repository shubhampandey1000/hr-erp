from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import attendance, auth, department, employee, leave, payroll
from app.core.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background cron scheduler
    start_scheduler()
    yield
    # Shutdown: Cleanly terminate threads
    shutdown_scheduler()

app = FastAPI(
    title="HR ERP System",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(employee.router)
app.include_router(auth.router)
app.include_router(department.router)
app.include_router(leave.router)
app.include_router(attendance.router)
app.include_router(payroll.router)

# @app.get("/")
# def test_db():
#     with engine.connect() as connection:
#         result = connection.execute(text("SELECT 1"))
#         return {"database_connection": "successful"}

