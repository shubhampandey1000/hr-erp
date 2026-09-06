from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract, or_

from app.models.attendance import Attendance, CompOffRequest
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType, LeaveBalance
from app.models.enums import AttendanceStatusEnum, LeaveStatusEnum, RoleEnum, CompOffStatusEnum
from app.schemas.attendance import ClockInRequest, ClockOutRequest, AttendanceManualCreate
from sqlalchemy.exc import IntegrityError

class AttendanceService:

    @staticmethod
    def _calculate_work_metrics(clock_in: datetime, clock_out: datetime, work_date: date) -> tuple[Decimal, Decimal, str]:
        duration_seconds = (clock_out - clock_in).total_seconds()
        
        # Round to 2 decimal places and cast via string to Decimal safely
        total_hours = Decimal(str(round(duration_seconds / 3600.0, 2)))
        is_weekend = work_date.weekday() in [5, 6]

        if is_weekend:
            if total_hours >= Decimal("8.0"):
                status_val = AttendanceStatusEnum.present.value
                overtime_hours = max(Decimal("0.0"), total_hours - Decimal("8.0"))
            elif total_hours >= Decimal("4.0"):
                status_val = AttendanceStatusEnum.half_day.value
                overtime_hours = Decimal("0.0")
            else:
                status_val = AttendanceStatusEnum.absent.value
                overtime_hours = Decimal("0.0")
            return total_hours, overtime_hours, status_val

        # Standard workday: 8 hours
        if total_hours >= Decimal("8.0"):
            status_val = AttendanceStatusEnum.present.value
            overtime_hours = max(Decimal("0.0"), total_hours - Decimal("8.0"))
        elif total_hours >= Decimal("4.0"):
            status_val = AttendanceStatusEnum.half_day.value
            overtime_hours = Decimal("0.0")
        else:
            status_val = AttendanceStatusEnum.absent.value
            overtime_hours = Decimal("0.0")

        return total_hours, overtime_hours, status_val

    @staticmethod
    def clock_in(db: Session, employee_id: int, data: ClockInRequest) -> Attendance:
        now = datetime.now(timezone.utc)
        today = now.date()

        # 1. Check if on approved leave
        approved_leave = (
            db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == LeaveStatusEnum.approved.value,
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
            )
            .first()
        )

        if approved_leave:
            raise HTTPException(
                status_code=400,
                detail="Cannot clock in: employee is marked on approved leave for today."
            )

        # 2. Check existing record
        record = (
            db.query(Attendance)
            .filter(Attendance.employee_id == employee_id, Attendance.work_date == today)
            .first()
        )

        if record:
            if record.clock_in is not None and record.clock_out is None:
                raise HTTPException(
                    status_code=400,
                    detail="Employee has already clocked in today and has not clocked out."
                )
            if record.clock_in is not None and record.clock_out is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Attendance session for today is already completed."
                )
            
        record = Attendance(
            employee_id=employee_id,
            work_date=today,
            clock_in=now,
            status=AttendanceStatusEnum.present.value,
            notes=data.notes,
        )

        db.add(record)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if "uq_employee_work_date" in str(exc.orig).lower():
                raise HTTPException(
                    status_code=400,
                    detail="Attendance record already exists for today."
                )
            raise HTTPException(
                status_code=400,
                detail="Could not record attendance due to a database constraint violation."
            )

        return (
            db.query(Attendance)
            .options(joinedload(Attendance.employee))
            .filter(Attendance.id == record.id)
            .first()
        )

    @staticmethod
    def clock_out(db: Session, employee_id: int, data: ClockOutRequest) -> Attendance:
        now = datetime.now(timezone.utc)
        today = now.date()

        record = (
            db.query(Attendance)
            .filter(Attendance.employee_id == employee_id, Attendance.work_date == today)
            .first()
        )

        if not record or record.clock_in is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot clock out: no active clock-in found for today."
            )

        if record.clock_out is not None:
            raise HTTPException(
                status_code=400,
                detail="Employee has already clocked out for today."
            )

        record.clock_out = now
        total_hours, overtime, final_status = AttendanceService._calculate_work_metrics(
            record.clock_in, record.clock_out, record.work_date
        )

        record.total_hours = total_hours
        record.overtime_hours = overtime
        record.status = final_status
        if data.notes:
            record.notes = f"{record.notes} | {data.notes}" if record.notes else data.notes

        db.commit()

        return (
            db.query(Attendance)
            .options(joinedload(Attendance.employee))
            .filter(Attendance.id == record.id)
            .first()
        )

    @staticmethod
    def get_attendance(
        db: Session,
        current_user: Employee,
        work_date: date | None = None,
        employee_id: int | None = None,
        skip: int = 0,
        limit: int = 20
    ) -> dict:
        query = db.query(Attendance).options(joinedload(Attendance.employee))

        # Authorization filtering
        if current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]:
            if employee_id:
                query = query.filter(Attendance.employee_id == employee_id)
        elif current_user.role in [RoleEnum.manager.value, RoleEnum.manager]:
            direct_report_ids = [emp.id for emp in current_user.direct_reports]
            allowed_ids = [current_user.id] + direct_report_ids
            if employee_id:
                if employee_id not in allowed_ids:
                    raise HTTPException(status_code=403, detail="Access denied.")
                query = query.filter(Attendance.employee_id == employee_id)
            else:
                query = query.filter(Attendance.employee_id.in_(allowed_ids))
        else:
            query = query.filter(Attendance.employee_id == current_user.id)

        if work_date:
            query = query.filter(Attendance.work_date == work_date)

        total = query.count()
        items = query.order_by(Attendance.work_date.desc(), Attendance.id.desc()).offset(skip).limit(limit).all()

        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @staticmethod
    def get_monthly_summary(
        db: Session,
        current_user: Employee,
        employee_id: int,
        year: int,
        month: int
    ) -> dict:
        # Hierarchical scope validation
        is_admin_or_hr = current_user.role in [
            RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr
        ]
        is_manager = current_user.role in [RoleEnum.manager.value, RoleEnum.manager]

        if not is_admin_or_hr:
            if is_manager:
                direct_report_ids = [emp.id for emp in current_user.direct_reports]
                if employee_id != current_user.id and employee_id not in direct_report_ids:
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: You can only view summaries for yourself and direct reports."
                    )
            else:
                if employee_id != current_user.id:
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: You can only view your own attendance summary."
                    )

        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee_id,
                extract("year", Attendance.work_date) == year,
                extract("month", Attendance.work_date) == month,
            )
            .all()
        )

        present_days = sum(1 for r in records if r.status == AttendanceStatusEnum.present.value)
        half_days = sum(1 for r in records if r.status == AttendanceStatusEnum.half_day.value)
        absent_days = sum(1 for r in records if r.status == AttendanceStatusEnum.absent.value)
        leave_days = sum(1 for r in records if r.status == AttendanceStatusEnum.on_leave.value)
        total_hours = sum((r.total_hours for r in records), Decimal("0.0"))
        overtime_hours = sum((r.overtime_hours for r in records), Decimal("0.0"))

        return {
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "present_days": present_days,
            "half_days": half_days,
            "absent_days": absent_days,
            "leave_days": leave_days,
            "total_hours_worked": total_hours,
            "total_overtime_hours": overtime_hours,
        }

    @staticmethod
    def request_comp_off(db: Session, employee_id: int, worked_date: date, reason: str) -> CompOffRequest:
        if worked_date.weekday() not in [5, 6]:
            raise HTTPException(
                status_code=400,
                detail="Comp Off can only be claimed for work performed on weekends (Saturday/Sunday)."
            )

        if worked_date > datetime.now(timezone.utc).date():
            raise HTTPException(
                status_code=400,
                detail="Cannot request Comp Off for future dates."
            )

        att = (
            db.query(Attendance)
            .filter(Attendance.employee_id == employee_id, Attendance.work_date == worked_date)
            .first()
        )

        if not att or att.clock_out is None:
            raise HTTPException(
                status_code=400,
                detail="No completed attendance record found for this weekend date."
            )

        if att.total_hours < Decimal("4.0"):
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient work hours ({att.total_hours} hrs). Minimum 4 hours required for Comp Off."
            )

        credit_days = Decimal("1.0") if att.total_hours >= Decimal("8.0") else Decimal("0.5")

        existing = (
            db.query(CompOffRequest)
            .filter(CompOffRequest.employee_id == employee_id, CompOffRequest.worked_date == worked_date)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail="A Comp Off request has already been submitted for this date."
            )

        req = CompOffRequest(
            employee_id=employee_id,
            worked_date=worked_date,
            credit_days=credit_days,
            reason=reason,
            status=CompOffStatusEnum.pending.value,
        )
        db.add(req)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if "uq_employee_worked_date_compoff" in str(exc.orig).lower():
                raise HTTPException(
                    status_code=409,
                    detail="A Comp Off request has already been submitted for this date."
                )
            raise HTTPException(
                status_code=400,
                detail="Could not create the Comp Off request due to a database constraint violation."
            )
        db.refresh(req)
        return req

    @staticmethod
    def get_comp_off_requests(
        db: Session,
        current_user: Employee,
        status_filter: CompOffStatusEnum | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> dict:
        query = (
            db.query(CompOffRequest)
            .options(
                joinedload(CompOffRequest.employee),
                joinedload(CompOffRequest.approver)
            )
        )

        # Scoped access: Admin/HR -> All, Manager -> Self + Direct Reports, Employee -> Self
        if current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]:
            pass
        elif current_user.role in [RoleEnum.manager.value, RoleEnum.manager]:
            direct_report_ids = [emp.id for emp in current_user.direct_reports]
            query = query.filter(
                or_(
                    CompOffRequest.employee_id == current_user.id,
                    CompOffRequest.employee_id.in_(direct_report_ids)
                )
            )
        else:
            query = query.filter(CompOffRequest.employee_id == current_user.id)

        if status_filter:
            val = status_filter.value if isinstance(status_filter, CompOffStatusEnum) else status_filter
            query = query.filter(CompOffRequest.status == val)

        total = query.count()
        items = query.order_by(CompOffRequest.created_at.desc()).offset(skip).limit(limit).all()

        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @staticmethod
    def approve_comp_off(
        db: Session,
        request_id: int,
        approver: Employee,
        action_reason: str | None
    ) -> CompOffRequest:
        # Row-level lock on the request itself to eliminate race conditions
        req = (
            db.query(CompOffRequest)
            .options(joinedload(CompOffRequest.employee))
            .filter(CompOffRequest.id == request_id)
            .with_for_update()
            .first()
        )
        if not req:
            raise HTTPException(
                status_code=404,
                detail="Comp Off request not found."
            )

        if req.status != CompOffStatusEnum.pending.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve request with status '{req.status}'."
            )

        is_admin_or_hr = approver.role in [
            RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr
        ]
        is_direct_manager = req.employee.manager_id == approver.id

        if not (is_admin_or_hr or is_direct_manager):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to approve this Comp Off request."
            )

        # Serialize balance creation and updates for this employee.
        db.query(Employee).filter(Employee.id == req.employee_id).with_for_update().one()

        # Find or create 'Compensatory Off' leave type
        comp_off_type = (
            db.query(LeaveType)
            .filter(LeaveType.name == "Compensatory Off", LeaveType.is_active.is_(True))
            .first()
        )

        if not comp_off_type:
            comp_off_type = LeaveType(
                name="Compensatory Off",
                description="Earned compensatory off from weekend work",
                default_days_per_year=Decimal("0.0"),
            )
            db.add(comp_off_type)
            db.flush()

        # Credit balance for the worked year with row lock
        year = req.worked_date.year
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.leave_type_id == comp_off_type.id,
                LeaveBalance.year == year,
            )
            .with_for_update()
            .first()
        )

        if not balance:
            balance = LeaveBalance(
                employee_id=req.employee_id,
                leave_type_id=comp_off_type.id,
                year=year,
                allocated_days=req.credit_days,
                used_days=Decimal("0.0"),
            )
            db.add(balance)
        else:
            balance.allocated_days += req.credit_days

        req.status = CompOffStatusEnum.approved.value
        req.approver_id = approver.id
        req.action_reason = action_reason
        req.action_taken_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(req)
        return req

    @staticmethod
    def reject_comp_off(db: Session, request_id: int, approver: Employee, action_reason: str | None) -> CompOffRequest:
        req = (
            db.query(CompOffRequest)
            .options(
                joinedload(CompOffRequest.employee),
                joinedload(CompOffRequest.approver)
            )
            .filter(CompOffRequest.id == request_id)
            .with_for_update()
            .first()
        )
        if not req:
            raise HTTPException(
                status_code=404,
                detail="Comp Off request not found."
            )

        if req.status != CompOffStatusEnum.pending.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject request with status '{req.status}'."
            )

        is_admin_or_hr = approver.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
        is_direct_manager = req.employee.manager_id == approver.id

        if not (is_admin_or_hr or is_direct_manager):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to reject this Comp Off request."
            )

        req.status = CompOffStatusEnum.rejected.value
        req.approver_id = approver.id
        req.action_reason = action_reason
        req.action_taken_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(req)
        return req