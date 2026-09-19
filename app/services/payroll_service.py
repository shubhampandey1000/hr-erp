import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract

from app.models.employee import Employee
from app.models.payroll import SalaryStructure, PayrollRecord
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.models.enums import AttendanceStatusEnum, LeaveStatusEnum, PayrollStatusEnum, RoleEnum
from app.schemas.payroll import (
    SalaryStructureCreate,
    ProcessMonthlyPayrollRequest,
    UpdatePayrollStatusRequest,
)


class PayrollService:

    VALID_TRANSITIONS = {
        PayrollStatusEnum.draft.value: [PayrollStatusEnum.processed.value],
        PayrollStatusEnum.processed.value: [PayrollStatusEnum.paid.value, PayrollStatusEnum.draft.value],
        PayrollStatusEnum.paid.value: [],  # Terminal state: cannot be modified or moved back
    }

    @staticmethod
    def _round_currency(val: Decimal) -> Decimal:
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # -------------------------------------------------------------
    # Salary Structure Management
    # -------------------------------------------------------------

    @staticmethod
    def create_or_update_structure(db: Session, data: SalaryStructureCreate) -> SalaryStructure:
        emp = db.query(Employee).filter(Employee.id == data.employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found.")

        existing = (
            db.query(SalaryStructure)
            .filter(SalaryStructure.employee_id == data.employee_id)
            .with_for_update()
            .first()
        )

        if existing:
            existing.base_salary = data.base_salary
            existing.hra = data.hra
            existing.special_allowance = data.special_allowance
            existing.pf_deduction = data.pf_deduction
            existing.professional_tax = data.professional_tax
            db.commit()
            db.refresh(existing)
            return existing

        structure = SalaryStructure(
            employee_id=data.employee_id,
            base_salary=data.base_salary,
            hra=data.hra,
            special_allowance=data.special_allowance,
            pf_deduction=data.pf_deduction,
            professional_tax=data.professional_tax,
        )
        db.add(structure)
        db.commit()
        db.refresh(structure)
        return structure

    @staticmethod
    def get_structure_by_employee(db: Session, employee_id: int) -> SalaryStructure:
        structure = (
            db.query(SalaryStructure)
            .filter(SalaryStructure.employee_id == employee_id)
            .first()
        )
        if not structure:
            raise HTTPException(
                status_code=404,
                detail=f"Salary structure not defined for employee ID {employee_id}."
            )
        return structure

    # -------------------------------------------------------------
    # Payroll Processing Engine
    # -------------------------------------------------------------

    @staticmethod
    def _calculate_employee_month_payroll(
        db: Session,
        employee: Employee,
        year: int,
        month: int,
    ) -> PayrollRecord:
        structure = (
            db.query(SalaryStructure)
            .filter(SalaryStructure.employee_id == employee.id)
            .first()
        )
        if not structure:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot process payroll: Salary structure missing for employee {employee.employee_code}."
            )

        _, days_in_month = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, days_in_month)

        weekend_days = sum(
            1 for day in range(1, days_in_month + 1)
            if date(year, month, day).weekday() in [5, 6]
        )

        attendance_records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee.id,
                extract("year", Attendance.work_date) == year,
                extract("month", Attendance.work_date) == month,
            )
            .all()
        )

        present_days = sum(Decimal("1.0") for r in attendance_records if r.status == AttendanceStatusEnum.present.value)
        half_days = sum(Decimal("1.0") for r in attendance_records if r.status == AttendanceStatusEnum.half_day.value)

        approved_leaves = (
            db.query(LeaveRequest)
            .options(joinedload(LeaveRequest.leave_type))
            .filter(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status == LeaveStatusEnum.approved.value,
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
            .all()
        )

        paid_leave_days = Decimal("0.0")
        unpaid_leave_days = Decimal("0.0")

        for req in approved_leaves:
            req_start = max(req.start_date, start_date)
            req_end = min(req.end_date, end_date)
            leave_is_paid = bool(req.leave_type is not None and req.leave_type.is_paid)

            curr = req_start
            while curr <= req_end:
                if curr.weekday() not in [5, 6]:
                    if leave_is_paid:
                        paid_leave_days += Decimal("1.0")
                    else:
                        unpaid_leave_days += Decimal("1.0")
                curr = curr.fromordinal(curr.toordinal() + 1)

        total_paid_units = present_days + (half_days * Decimal("0.5")) + paid_leave_days + Decimal(str(weekend_days))
        month_total_dec = Decimal(str(days_in_month))
        
        lop_days = max(Decimal("0.0"), month_total_dec - total_paid_units)
        # Combine explicit unpaid leave days and attendance deficit
        unpaid_leave_days = max(unpaid_leave_days, lop_days)

        gross_salary = structure.base_salary + structure.hra + structure.special_allowance
        per_day_rate = gross_salary / month_total_dec
        lop_deduction = PayrollService._round_currency(per_day_rate * unpaid_leave_days)

        pf_deduction = PayrollService._round_currency(structure.pf_deduction)
        professional_tax = PayrollService._round_currency(structure.professional_tax)
        total_deductions = lop_deduction + pf_deduction + professional_tax

        net_salary = max(Decimal("0.00"), gross_salary - total_deductions)

        record = (
            db.query(PayrollRecord)
            .filter(
                PayrollRecord.employee_id == employee.id,
                PayrollRecord.year == year,
                PayrollRecord.month == month,
            )
            .with_for_update()
            .first()
        )

        if record:
            if record.status == PayrollStatusEnum.paid.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payroll for {employee.employee_code} for {year}-{month:02d} is already marked as PAID and cannot be regenerated."
                )
            record.total_days_in_month = days_in_month
            record.present_days = present_days
            record.half_days = half_days
            record.paid_leave_days = paid_leave_days
            record.unpaid_leave_days = unpaid_leave_days
            record.weekend_days = weekend_days
            record.proration_basis = "calendar_days"
            record.gross_salary = gross_salary
            record.lop_deduction = lop_deduction
            record.pf_deduction = pf_deduction
            record.professional_tax = professional_tax
            record.total_deductions = total_deductions
            record.net_salary = net_salary
            record.status = PayrollStatusEnum.processed.value
        else:
            record = PayrollRecord(
                employee_id=employee.id,
                year=year,
                month=month,
                proration_basis="calendar_days",
                total_days_in_month=days_in_month,
                present_days=present_days,
                half_days=half_days,
                paid_leave_days=paid_leave_days,
                unpaid_leave_days=unpaid_leave_days,
                weekend_days=weekend_days,
                gross_salary=gross_salary,
                lop_deduction=lop_deduction,
                pf_deduction=pf_deduction,
                professional_tax=professional_tax,
                total_deductions=total_deductions,
                net_salary=net_salary,
                status=PayrollStatusEnum.processed.value,
            )
            db.add(record)

        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def process_monthly_payroll(
        db: Session,
        payload: ProcessMonthlyPayrollRequest
    ) -> dict:
        if payload.employee_id:
            emp = (
                db.query(Employee)
                .filter(Employee.id == payload.employee_id, Employee.is_active.is_(True))
                .first()
            )
            if not emp:
                raise HTTPException(status_code=404, detail="Active employee not found.")
            record = PayrollService._calculate_employee_month_payroll(db, emp, payload.year, payload.month)
            return {"processed": [record], "skipped": []}

        active_employees = db.query(Employee).filter(Employee.is_active.is_(True)).all()
        processed = []
        skipped = []

        for emp in active_employees:
            has_structure = (
                db.query(SalaryStructure.id)
                .filter(SalaryStructure.employee_id == emp.id)
                .first()
            )
            if not has_structure:
                skipped.append({
                    "employee_id": emp.id,
                    "employee_code": emp.employee_code,
                    "reason": "Missing salary structure"
                })
                continue

            try:
                rec = PayrollService._calculate_employee_month_payroll(db, emp, payload.year, payload.month)
                processed.append(rec)
            except HTTPException as e:
                skipped.append({
                    "employee_id": emp.id,
                    "employee_code": emp.employee_code,
                    "reason": e.detail
                })

        return {"processed": processed, "skipped": skipped}

    @staticmethod
    def get_payroll_records(
        db: Session,
        current_user: Employee,
        year: int | None = None,
        month: int | None = None,
        employee_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        query = db.query(PayrollRecord).options(joinedload(PayrollRecord.employee))

        is_admin_or_hr = current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
        if is_admin_or_hr:
            if employee_id:
                query = query.filter(PayrollRecord.employee_id == employee_id)
        else:
            query = query.filter(PayrollRecord.employee_id == current_user.id)

        if year:
            query = query.filter(PayrollRecord.year == year)
        if month:
            query = query.filter(PayrollRecord.month == month)

        total = query.count()
        items = query.order_by(PayrollRecord.year.desc(), PayrollRecord.month.desc()).offset(skip).limit(limit).all()

        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @staticmethod
    def update_status(
        db: Session,
        record_id: int,
        payload: UpdatePayrollStatusRequest
    ) -> PayrollRecord:
        record = (
            db.query(PayrollRecord)
            .filter(PayrollRecord.id == record_id)
            .with_for_update()
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Payroll record not found.")

        target_status = payload.status.value if hasattr(payload.status, "value") else str(payload.status)

        if record.status == PayrollStatusEnum.paid.value:
            raise HTTPException(
                status_code=400,
                detail="Payroll record is already marked as PAID and cannot be modified."
            )

        allowed = PayrollService.VALID_TRANSITIONS.get(record.status, [])
        if target_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from '{record.status}' to '{target_status}'. Allowed: {allowed}"
            )

        if target_status == PayrollStatusEnum.paid.value and not payload.payment_date:
            raise HTTPException(
                status_code=400,
                detail="payment_date is required when transitioning status to PAID."
            )

        record.status = target_status
        if payload.payment_date:
            record.payment_date = payload.payment_date
        if payload.notes:
            record.notes = payload.notes

        db.commit()
        db.refresh(record)
        return record