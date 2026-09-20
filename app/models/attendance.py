from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, Numeric, String, Index, func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import AttendanceStatusEnum, CompOffStatusEnum


class Attendance(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    work_date = Column(Date, nullable=False, index=True)

    clock_in = Column(DateTime(timezone=True), nullable=True)
    clock_out = Column(DateTime(timezone=True), nullable=True)

    total_hours = Column(Numeric(4, 2), nullable=False, default=0.0)
    overtime_hours = Column(Numeric(4, 2), nullable=False, default=0.0)

    status = Column(String(50), nullable=False, default=AttendanceStatusEnum.absent.value, server_default=AttendanceStatusEnum.absent.value)

    notes = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee")
    organization = relationship("Organization")

    __table_args__ = (
        Index(
            "uq_employee_work_date",
            "employee_id",
            "work_date",
            unique=True
        ),
    )


class CompOffRequest(Base):
    __tablename__ = "comp_off_requests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    worked_date = Column(Date, nullable=False)
    credit_days = Column(Numeric(4, 1), nullable=False)
    reason = Column(String(500), nullable=False)

    status = Column(
        String(50),
        nullable=False,
        default=CompOffStatusEnum.pending.value,
        server_default=CompOffStatusEnum.pending.value
    )

    approver_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    action_reason = Column(String(500), nullable=True)
    action_taken_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    organization = relationship("Organization")

    __table_args__ = (
        Index("uq_employee_worked_date_compoff", "employee_id", "worked_date", unique=True),
    )