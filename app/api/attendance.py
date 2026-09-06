from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.employee import Employee
from app.models.enums import RoleEnum, CompOffStatusEnum
from app.schemas.common import PaginatedResponse
from app.schemas.attendance import (
    ClockInRequest,
    ClockOutRequest,
    AttendanceResponse,
    MonthlyAttendanceSummary,
)
from app.services.attendance_service import AttendanceService
from app.core.scheduler import process_daily_attendance_job
from app.schemas.attendance import (
    CompOffCreate,
    CompOffDecision,
    CompOffResponse,
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/clock-in", response_model=AttendanceResponse)
def clock_in(
    data: ClockInRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return AttendanceService.clock_in(db, current_user.id, data)


@router.post("/clock-out", response_model=AttendanceResponse)
def clock_out(
    data: ClockOutRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return AttendanceService.clock_out(db, current_user.id, data)


@router.get("/", response_model=PaginatedResponse[AttendanceResponse])
def list_attendance(
    work_date: date | None = None,
    employee_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return AttendanceService.get_attendance(db, current_user, work_date, employee_id, skip, limit)


@router.get("/summary/monthly", response_model=MonthlyAttendanceSummary)
def get_monthly_summary(
    employee_id: int,
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    current_date = datetime.now(timezone.utc).date()
    return AttendanceService.get_monthly_summary(
        db=db,
        current_user=current_user,
        employee_id=employee_id,
        year=year if year is not None else current_date.year,
        month=month if month is not None else current_date.month,
    )


@router.post("/comp-off/request", response_model=CompOffResponse)
def request_comp_off(
    data: CompOffCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return AttendanceService.request_comp_off(
        db=db,
        employee_id=current_user.id,
        worked_date=data.worked_date,
        reason=data.reason
    )

@router.get("/comp-off", response_model=PaginatedResponse[CompOffResponse])
def list_comp_off_requests(
    status: CompOffStatusEnum | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return AttendanceService.get_comp_off_requests(
        db=db,
        current_user=current_user,
        status_filter=status,
        skip=skip,
        limit=limit,
    )

@router.post("/comp-off/{request_id}/approve", response_model=CompOffResponse)
def approve_comp_off(
    request_id: int,
    decision: CompOffDecision,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr, RoleEnum.manager)),
):
    return AttendanceService.approve_comp_off(
        db=db,
        request_id=request_id,
        approver=current_user,
        action_reason=decision.action_reason,
    )


@router.post("/comp-off/{request_id}/reject", response_model=CompOffResponse)
def reject_comp_off(
    request_id: int,
    decision: CompOffDecision,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr, RoleEnum.manager)),
):
    return AttendanceService.reject_comp_off(
        db=db,
        request_id=request_id,
        approver=current_user,
        action_reason=decision.action_reason,
    )


@router.post("/run-eod-job")
def trigger_daily_attendance_run(
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    process_daily_attendance_job()
    return {"message": "Daily EOD attendance processing executed successfully."}

