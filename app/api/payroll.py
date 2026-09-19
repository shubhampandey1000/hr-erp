from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.employee import Employee
from app.models.enums import RoleEnum
from app.schemas.payroll import (
    SalaryStructureCreate,
    SalaryStructureResponse,
    ProcessMonthlyPayrollRequest,
    PayrollRecordResponse,
    UpdatePayrollStatusRequest,
    BatchPayrollResponse,
)
from app.services.payroll_service import PayrollService
from app.models.payroll import PayrollRecord
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/payroll", tags=["Payroll Management"])


# ==========================================
# Salary Structures (Admin / HR only)
# ==========================================

@router.post("/salary-structures", response_model=SalaryStructureResponse)
def set_salary_structure(
    payload: SalaryStructureCreate,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return PayrollService.create_or_update_structure(db, payload)


@router.get("/salary-structures/{employee_id}", response_model=SalaryStructureResponse)
def get_salary_structure(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    # Admins/HR can view all, employees can view only their own
    is_admin_or_hr = current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
    if not is_admin_or_hr and current_user.id != employee_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return PayrollService.get_structure_by_employee(db, employee_id)


# ==========================================
# Payroll Processing (Admin / HR only)
# ==========================================

@router.post("/process", response_model=BatchPayrollResponse)
def process_payroll(
    payload: ProcessMonthlyPayrollRequest,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return PayrollService.process_monthly_payroll(db, payload)


# ==========================================
# Payslips / Payroll Records
# ==========================================

@router.get("/records")
def list_payroll_records(
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    employee_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    return PayrollService.get_payroll_records(
        db=db,
        current_user=current_user,
        year=year,
        month=month,
        employee_id=employee_id,
        skip=skip,
        limit=limit,
    )


@router.patch("/records/{record_id}/status", response_model=PayrollRecordResponse)
def update_payroll_status(
    record_id: int,
    payload: UpdatePayrollStatusRequest,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return PayrollService.update_status(db, record_id, payload)


@router.get("/records/{record_id}/payslip/pdf")
def download_payslip_pdf(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    record = (
        db.query(PayrollRecord)
        .options(joinedload(PayrollRecord.employee))
        .filter(PayrollRecord.id == record_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found.")

    is_admin_or_hr = current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
    if not is_admin_or_hr and record.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    pdf_buffer = PDFService.generate_payslip_pdf(record)
    filename = f"payslip_{record.employee.employee_code}_{record.year}_{record.month:02d}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )