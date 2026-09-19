import os
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.employee import Employee
from app.models.leave import LeaveType
from app.models.enums import RoleEnum, EmploymentStatusEnum

# Use a separate test database or an in-memory SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_hr_erp.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # <-- Releases the Windows file lock on SQLite
    if os.path.exists("./test_hr_erp.db"):
        try:
            os.remove("./test_hr_erp.db")
        except PermissionError:
            pass


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_admin(db_session) -> Employee:
    admin = Employee(
        first_name="Admin",
        last_name="User",
        email="admin_test@example.com",
        hashed_password=hash_password("testpass"),  # <-- updated
        role=RoleEnum.admin.value,
        employee_code="EMP_TEST_ADMIN",
        is_active=True,
        employment_status=EmploymentStatusEnum.active.value,
        date_of_joining=date(2025, 1, 1),
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def test_employee(db_session) -> Employee:
    emp = Employee(
        first_name="Jane",
        last_name="Doe",
        email="jane_test@example.com",
        hashed_password=hash_password("testpass"),  # <-- updated
        role=RoleEnum.employee.value,
        employee_code="EMP_TEST_001",
        is_active=True,
        employment_status=EmploymentStatusEnum.active.value,
        date_of_joining=date(2025, 1, 1),
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def admin_token(test_admin) -> str:
    return create_access_token(data={"sub": test_admin.email})


@pytest.fixture
def employee_token(test_employee) -> str:
    return create_access_token(data={"sub": test_employee.email})


@pytest.fixture
def seed_leave_types(db_session):
    casual = LeaveType(name="Casual Leave", is_paid=True, default_days_per_year=12.0)
    lop = LeaveType(name="Loss of Pay (LOP)", is_paid=False, default_days_per_year=0.0)
    db_session.add_all([casual, lop])
    db_session.commit()
    return {"casual": casual, "lop": lop}