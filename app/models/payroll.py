from decimal import Decimal
from sqlalchemy import Column, Integer, ForeignKey, Numeric, String, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base
from app.models.enums import PayrollStatusEnum

class SalaryStructure(Base):
    __tablename__ = "salary_structures"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id = Column(
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    base_salary = Column(Numeric(12, 2), nullable=False)
    hra = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    special_allowance = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    pf_deduction = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    professional_tax = Column(Numeric(12, 2), default=Decimal("200.00"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    employee = relationship("Employee", back_populates="salary_structure")
    organization = relationship("Organization")


class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    proration_basis = Column(String(50), default="calendar_days", nullable=False)

    # Attendance Breakdown
    total_days_in_month = Column(Integer, nullable=False)
    present_days = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    half_days = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    paid_leave_days = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    unpaid_leave_days = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    weekend_days = Column(Integer, default=0, nullable=False)

    # Earnings & Deductions
    gross_salary = Column(Numeric(12, 2), nullable=False)
    lop_deduction = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    pf_deduction = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    professional_tax = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)
    net_salary = Column(Numeric(12, 2), nullable=False)

    status = Column(String(20), default=PayrollStatusEnum.draft.value, nullable=False)
    payment_date = Column(Date, nullable=True)
    notes = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    employee = relationship("Employee", back_populates="payroll_records")
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("employee_id", "year", "month", name="uq_employee_payroll_month"),
    )