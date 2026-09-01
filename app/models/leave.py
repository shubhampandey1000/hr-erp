from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Numeric, Index, text, func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import LeaveStatusEnum

class LeaveType(Base):
    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(225), nullable=True)
    default_days_per_year = Column(Numeric(4, 1), nullable=False, default=12.0) 
    is_active = Column(Boolean, default=True, server_default=text("true"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False) 

    balances = relationship("LeaveBalance", back_populates="leave_type")
    requests = relationship("LeaveRequest", back_populates="leave_type")

    __table_args__ = (
        Index(
            "uq_active_leave_type_name",
            "name",
            unique=True,
            postgresql_where=(is_active.is_(True))
        ),
    )

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=False)
    year = Column(Integer, nullable=False)
    allocated_days = Column(Numeric(4, 1), nullable=False, default=0.0)
    used_days = Column(Numeric(4, 1), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee")
    leave_type = relationship("LeaveType", back_populates="balances")

    __table_args__ = (
        Index(
            "uq_employee_leave_year",
            "employee_id",
            "leave_type_id",
            "year",
            unique=True
        ),
    )

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days = Column(Numeric(4, 1), nullable=False)
    reason = Column(String(500), nullable=False)

    status = Column(
        String(50),
        nullable=False,
        default=LeaveStatusEnum.pending.value,
        server_default=LeaveStatusEnum.pending.value
    )

    approver_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    action_reason = Column(String(500), nullable=True)
    action_taken_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    approver = relationship("Employee", foreign_keys=[approver_id])
    leave_type = relationship("LeaveType", back_populates="requests")

    