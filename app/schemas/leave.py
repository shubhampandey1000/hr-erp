from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import LeaveStatusEnum
from app.schemas.common import EmployeeBasic


# ===================== LEAVE TYPE SCHEMAS =====================

class LeaveTypeBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(None, max_length=255)
    default_days_per_year: Decimal = Field(ge=0, decimal_places=1)

class LeaveTypeCreate(LeaveTypeBase):
    pass

class LeaveTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=255)
    default_days_per_year: Decimal | None = Field(None, ge=0, decimal_places=1)
    is_active: bool | None = None

class LeaveTypeResponse(LeaveTypeBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===================== LEAVE BALANCE SCHEMAS =====================


class LeaveBalanceBase(BaseModel):
    employee_id: int
    leave_type_id: int
    year: int
    allocated_days: Decimal = Field(ge=0, decimal_places=1)
    used_days: Decimal = Field(default=Decimal("0.0"), ge=0, decimal_places=1)

class LeaveBalanceCreate(BaseModel):
    employee_id: int
    leave_type_id: int
    year: int
    allocated_days: Decimal = Field(gt=0, decimal_places=1)

class LeaveBalanceResponse(LeaveBalanceBase):
    id: int
    remaining_days: Decimal
    leave_type: LeaveTypeResponse

    model_config = ConfigDict(from_attributes=True)

# ===================== LEAVE REQUEST SCHEMAS =====================

class LeaveRequestCreate(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=3, max_length=500)

class LeaveDecision(BaseModel):
    action_reason: str | None = Field(None, max_length=500)

class LeaveRequestResponse(BaseModel):
    id: int
    employee_id: int
    start_date: date
    end_date: date
    days: Decimal
    reason: str
    status: LeaveStatusEnum
    approver_id: int | None = None
    action_reason: str | None = None
    action_taken_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    employee: EmployeeBasic
    leave_type: LeaveTypeResponse
    approver: EmployeeBasic | None = None

    model_config = ConfigDict(from_attributes=True)



    