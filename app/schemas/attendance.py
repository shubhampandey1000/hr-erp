from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import AttendanceStatusEnum, CompOffStatusEnum
from app.schemas.common import EmployeeBasic


class ClockInRequest(BaseModel):
    notes: str | None = Field(None, max_length=255)

class ClockOutRequest(BaseModel):
    notes: str | None = Field(None, max_length=255)

class AttendanceManualCreate(BaseModel):
    employee_id: int
    work_date: date
    clock_in: datetime | None = None
    clock_out: datetime | None = None
    status: AttendanceStatusEnum
    notes: str | None = Field(None, max_length=255)

class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    work_date: date
    clock_in: datetime | None = None
    clock_out: datetime | None = None
    total_hours: Decimal
    overtime_hours: Decimal
    status: AttendanceStatusEnum
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    employee: EmployeeBasic

    model_config = ConfigDict(from_attributes=True)

class MonthlyAttendanceSummary(BaseModel):
    employee_id: int
    year: int
    month: int
    present_days: int
    half_days: int
    absent_days: int
    leave_days: int
    total_hours_worked: Decimal
    total_overtime_hours: Decimal


class CompOffCreate(BaseModel):
    worked_date: date
    reason: str = Field(..., min_length=5, max_length=500)


class CompOffDecision(BaseModel):
    action_reason: str | None = Field(None, max_length=500)


class CompOffResponse(BaseModel):
    id: int
    employee_id: int
    worked_date: date
    credit_days: Decimal
    reason: str
    status: CompOffStatusEnum
    approver_id: int | None = None
    action_reason: str | None = None
    action_taken_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    employee: EmployeeBasic
    approver: EmployeeBasic | None = None

    model_config = ConfigDict(from_attributes=True)