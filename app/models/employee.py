from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, func, text, ForeignKey, Index
from app.core.database import Base
from app.models.enums import RoleEnum, EmploymentStatusEnum
from sqlalchemy.orm import relationship, remote

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    email = Column(String(150), nullable=False)
    employee_code = Column(String(20), nullable=False)

    phone = Column(String(20))
    designation = Column(String(100))
    date_of_joining = Column(Date)
    is_active = Column(Boolean, default=True, server_default=text("true"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default=RoleEnum.employee.value, server_default=text("'employee'"), nullable=False)
    employment_status = Column(String(50), nullable=False, default=EmploymentStatusEnum.active.value, server_default=EmploymentStatusEnum.active.value)
    termination_date = Column(Date, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable = True)
    department = relationship("Department", back_populates = "employees")
    organization = relationship("Organization")

    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    manager = relationship(
        "Employee",
        remote_side=[id],
        back_populates="direct_reports"
    )
    direct_reports = relationship(
        "Employee",
        back_populates="manager",
        primaryjoin="and_(Employee.id == remote(Employee.manager_id), Employee.is_active == True)"
    )

    salary_structure = relationship("SalaryStructure", back_populates="employee", uselist=False, cascade="all, delete-orphan")
    payroll_records = relationship("PayrollRecord", back_populates="employee", cascade="all, delete-orphan")


    __table_args__ = (
        Index(
            "uq_active_employee_email",
            "organization_id",
            "email",
            unique = True,
            postgresql_where=(is_active.is_(True))
        ),
        Index(
            "uq_active_employee_code",
            "organization_id",
            "employee_code",
            unique = True,
            postgresql_where=(is_active.is_(True))
        ),
    )
    