import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from rq.job import Job
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.queue import task_queue
from app.jobs.payroll_jobs import run_payroll_job, run_payslip_job
from app.models.employee import Employee
from app.models.enums import RoleEnum
from app.schemas.payroll import (
    PayrollRecordResponse,
    ProcessMonthlyPayrollRequest,
    SalaryStructureCreate,
    SalaryStructureResponse,
    UpdatePayrollStatusRequest,
)
from app.services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["Payroll Management"])


# ==========================================
# Salary Structures (Admin / HR only) — unchanged, no background work needed
# ==========================================

@router.post("/salary-structures", response_model=SalaryStructureResponse)
def set_salary_structure(
    payload: SalaryStructureCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return PayrollService.create_or_update_structure(db, payload, current_user)


@router.get("/salary-structures/{employee_id}", response_model=SalaryStructureResponse)
def get_salary_structure(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    is_admin_or_hr = current_user.role in [RoleEnum.admin.value, RoleEnum.admin, RoleEnum.hr.value, RoleEnum.hr]
    if not is_admin_or_hr and current_user.id != employee_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return PayrollService.get_structure_by_employee(db, employee_id, current_user)


# ==========================================
# Payroll Processing (Admin / HR only) — now async
# ==========================================

@router.post("/process")
def process_payroll(
    payload: ProcessMonthlyPayrollRequest,
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    job = task_queue.enqueue(
        run_payroll_job,
        current_user.id,
        payload.year,
        payload.month,
        payload.employee_id,
    )
    return {"job_id": job.id, "status": "queued"}


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
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return PayrollService.update_status(db, record_id, payload, current_user)


@router.post("/records/{record_id}/payslip/generate")
def generate_payslip(
    record_id: int,
    current_user: Employee = Depends(get_current_user),
):
    job = task_queue.enqueue(run_payslip_job, record_id, current_user.id)
    return {"job_id": job.id, "status": "queued"}


# ==========================================
# Job status + result retrieval — shared by both job types
# ==========================================

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=task_queue.connection)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job not found.") from e

    response = {"job_id": job.id, "status": job.get_status()}
    if job.is_finished:
        response["result"] = job.result
    elif job.is_failed:
        response["error"] = str(job.exc_info)
    return response


@router.get("/jobs/{job_id}/payslip-download")
def download_payslip_result(job_id: str):
    try:
        job = Job.fetch(job_id, connection=task_queue.connection)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Job not found.") from e

    if not job.is_finished:
        raise HTTPException(status_code=400, detail=f"Job is not finished yet (status: {job.get_status()}).")

    result = job.result
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    pdf_bytes = base64.b64decode(result["pdf_base64"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )