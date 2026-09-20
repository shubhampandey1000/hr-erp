from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.employee import Employee
from app.models.enums import RoleEnum, LeaveStatusEnum
from app.schemas.common import PaginatedResponse
from app.schemas.leave import (
    LeaveTypeCreate,
    LeaveTypeUpdate,
    LeaveTypeResponse,
    LeaveBalanceCreate,
    LeaveBalanceResponse,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveDecision,
)
from app.services.leave_service import LeaveService

router = APIRouter(prefix="/leaves", tags=["Leaves"])


# 1. Leave Types
@router.post("/types", response_model=LeaveTypeResponse)
def create_leave_type(
    data: LeaveTypeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return LeaveService.create_leave_type(db, data, current_user)


@router.get("/types", response_model=list[LeaveTypeResponse])
def get_leave_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return LeaveService.get_leave_types(db, include_inactive)


@router.put("/types/{leave_type_id}", response_model=LeaveTypeResponse)
def update_leave_type(
    leave_type_id: int,
    data: LeaveTypeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    return LeaveService.update_leave_type(db, leave_type_id, data)


# 2. Leave Balances
@router.post("/balances", response_model=LeaveBalanceResponse)
def assign_leave_balance(
    data: LeaveBalanceCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    balance = LeaveService.assign_leave_balance(db, data)
    return {
        "id": balance.id,
        "employee_id": balance.employee_id,
        "leave_type_id": balance.leave_type_id,
        "year": balance.year,
        "allocated_days": balance.allocated_days,
        "used_days": balance.used_days,
        "remaining_days": balance.allocated_days - balance.used_days,
        "leave_type": balance.leave_type,
    }


@router.get("/balances/my", response_model=list[LeaveBalanceResponse])
def get_my_balances(
    year: int = Query(default=2026),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return LeaveService.get_employee_balances(db, current_user.id, year)


@router.get("/balances/{employee_id}", response_model=list[LeaveBalanceResponse])
def get_employee_balances(
    employee_id: int,
    year: int = Query(default=2026),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr, RoleEnum.manager)),
):
    return LeaveService.get_employee_balances(db, employee_id, year)


# 3. Leave Requests
@router.post("/requests", response_model=LeaveRequestResponse)
def apply_leave(
    data: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return LeaveService.apply_leave(db, current_user.id, data)


@router.get("/requests", response_model=PaginatedResponse[LeaveRequestResponse])
def list_leave_requests(
    status: LeaveStatusEnum | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return LeaveService.get_leave_requests(db, current_user, status, skip, limit)


@router.post("/requests/{leave_request_id}/approve", response_model=LeaveRequestResponse)
def approve_leave(
    leave_request_id: int,
    decision: LeaveDecision,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr, RoleEnum.manager)),
):
    return LeaveService.approve_leave(db, leave_request_id, current_user, decision)


@router.post("/requests/{leave_request_id}/reject", response_model=LeaveRequestResponse)
def reject_leave(
    leave_request_id: int,
    decision: LeaveDecision,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr, RoleEnum.manager)),
):
    return LeaveService.reject_leave(db, leave_request_id, current_user, decision)