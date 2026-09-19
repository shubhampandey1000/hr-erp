from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PayrollStatusEnum

class SalaryStructureBase(BaseModel):
    base_salary: Decimal = Field(..., gt=0, decimal_places=2, description="Monthly basic pay (must be > 0)")
    hra: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2, description="House Rent Allowance")
    special_allowance: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    pf_deduction: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2, description="Monthly PF contribution")
    professional_tax: Decimal = Field(default=Decimal("200.00"), ge=0, decimal_places=2)

class SalaryStructureCreate(SalaryStructureBase):
    employee_id: int

class SalaryStructureUpdate(BaseModel):
    base_salary: Decimal | None = Field(None, gt=0, decimal_places=2)
    hra: Decimal | None = Field(None, ge=0, decimal_places=2)
    special_allowance: Decimal | None = Field(None, ge=0, decimal_places=2)
    pf_deduction: Decimal | None = Field(None, ge=0, decimal_places=2)
    professional_tax: Decimal | None = Field(None, ge=0, decimal_places=2)

class SalaryStructureResponse(SalaryStructureBase):
    id: int
    employee_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Payroll Run & Payslip Schemas
# ==========================================


class ProcessMonthlyPayrollRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    employee_id: int | None = Field(None, description="If None, processes batch for all active employees")

class PayrollRecordResponse(BaseModel):
    id: int
    employee_id: int
    year: int
    month: int
    proration_basis: str

    # Attendance Breakdown
    total_days_in_month: int
    present_days: Decimal
    half_days: Decimal
    paid_leave_days: Decimal
    unpaid_leave_days: Decimal
    weekend_days: int

    # Financial Breakdown
    gross_salary: Decimal
    lop_deduction: Decimal
    pf_deduction: Decimal
    professional_tax: Decimal
    total_deductions: Decimal
    net_salary: Decimal

    status: PayrollStatusEnum
    payment_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UpdatePayrollStatusRequest(BaseModel):
    status: PayrollStatusEnum
    payment_date: date | None = None
    notes: str | None = None

class SkippedEmployeePayroll(BaseModel):
    employee_id: int
    employee_code: str
    reason: str


class BatchPayrollResponse(BaseModel):
    processed: list[PayrollRecordResponse]
    skipped: list[SkippedEmployeePayroll]