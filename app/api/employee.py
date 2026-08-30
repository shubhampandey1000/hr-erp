from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.core.dependencies import require_roles
from app.models.enums import RoleEnum, EmploymentStatusEnum
from app.services.employee_service import EmployeeService
from app.schemas.common import PaginatedResponse, EmployeeBasic

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("/", response_model=EmployeeResponse)
def create_employee(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return EmployeeService.create_employee(
        db,
        employee,
        current_user
    )


@router.get("/", response_model=PaginatedResponse[EmployeeResponse])
def get_employees(
    search: str | None = None,
    department_id: int | None = None,
    manager_id: int | None = None,
    role: RoleEnum | None = None,
    employment_status: EmploymentStatusEnum | None = None,
    sort_by: str = Query("id", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(10, ge = 1, le = 100),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    return EmployeeService.get_employees(
        db = db,    
        search = search,
        department_id = department_id,
        manager_id=manager_id,
        role = role,
        employment_status=employment_status,
        sort_by= sort_by,
        sort_order=sort_order,
        skip = skip,
        limit = limit
        )


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    update_data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    return EmployeeService.update_employee(
        db,
        employee_id,
        update_data,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    return EmployeeService.get_employee_by_id(
        db,
        employee_id
    )


@router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    return EmployeeService.delete_employee(
        db,
        employee_id
    )


@router.put("/{employee_id}/role", response_model=EmployeeResponse)
def update_role(
    employee_id: int,
    role: RoleEnum,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    return EmployeeService.update_role(
        db,
        employee_id,
        role
    )

@router.get("/{employee_id}/direct-reports", response_model=list[EmployeeBasic])
def get_direct_reports(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr, RoleEnum.manager)),
):
    return EmployeeService.get_direct_reports(db, employee_id)

@router.post("/{employee_id}/reactivate", response_model=EmployeeResponse)
def reactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    """Reactivates a soft-deleted employee record."""
    return EmployeeService.reactivate_employee(db, employee_id)

