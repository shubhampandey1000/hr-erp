import base64

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.enums import RoleEnum
from app.models.payroll import PayrollRecord
from app.schemas.payroll import ProcessMonthlyPayrollRequest
from app.services.payroll_service import PayrollService
from app.services.pdf_service import PDFService


def run_payroll_job(
    current_user_id: int,
    year: int,
    month: int,
    employee_id: int | None = None,
    db: Session | None = None,
) -> dict:
    from fastapi import HTTPException

    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        current_user = db.query(Employee).filter(Employee.id == current_user_id).first()
        if not current_user:
            return {"error": f"Employee {current_user_id} not found"}

        payload = ProcessMonthlyPayrollRequest(year=year, month=month, employee_id=employee_id)
        try:
            result = PayrollService.process_monthly_payroll(db, payload, current_user)
        except HTTPException as e:
            return {"error": e.detail}

        return {
            "processed": [
                {
                    "id": r.id,
                    "employee_id": r.employee_id,
                    "employee_code": r.employee.employee_code if r.employee else None,
                    "year": r.year,
                    "month": r.month,
                    "total_days_in_month": r.total_days_in_month,
                    "weekend_days": r.weekend_days,
                    "unpaid_leave_days": str(r.unpaid_leave_days),
                    "gross_salary": str(r.gross_salary),
                    "lop_deduction": str(r.lop_deduction),
                    "total_deductions": str(r.total_deductions),
                    "net_salary": str(r.net_salary),
                    "status": r.status,
                }
                for r in result["processed"]
            ],
            "skipped": result["skipped"],
        }
    finally:
        if owns_session:
            db.close()


def run_payslip_job(record_id: int, current_user_id: int, db: Session | None = None) -> dict:
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload

        current_user = db.query(Employee).filter(Employee.id == current_user_id).first()
        if not current_user:
            return {"error": f"Employee {current_user_id} not found"}

        record = (
            db.query(PayrollRecord)
            .options(joinedload(PayrollRecord.employee))
            .filter(
                PayrollRecord.id == record_id,
                PayrollRecord.organization_id == current_user.organization_id,
            )
            .first()
        )
        if not record:
            return {"error": "Payroll record not found"}

        is_admin_or_hr = current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
        if not is_admin_or_hr and record.employee_id != current_user.id:
            return {"error": "Access denied"}

        pdf_buffer = PDFService.generate_payslip_pdf(record)
        pdf_bytes = pdf_buffer.read()
        filename = f"payslip_{record.employee.employee_code}_{record.year}_{record.month:02d}.pdf"

        return {
            "filename": filename,
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        }
    finally:
        if owns_session:
            db.close()