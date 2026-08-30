from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, func, text, ForeignKey, Index
from app.core.database import Base
from app.models.enums import RoleEnum
from sqlalchemy.orm import relationship

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
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
    department_id = Column(Integer, ForeignKey("departments.id"), nullable = True)
    department = relationship("Department", back_populates = "employees")


    __table_args__ = (
        Index(
            "uq_active_employee_email",
            "email",
            unique = True,
            postgresql_where=(is_active.is_(True))
        ),
        Index(
            "uq_active_employee_code",
            "employee_code",
            unique = True,
            postgresql_where=(is_active.is_(True))
        ),
    )
    