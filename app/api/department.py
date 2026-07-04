from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse
)
from app.services.department_service import DepartmentService
from app.core.dependencies import get_current_user

router = APIRouter(
    prefix="/departments",
    tags=["Departments"]
)

@router.post("/", response_model=DepartmentResponse)
def create_department(
    department: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("admin"))
):
    return DepartmentService.create_department(
        db,
        department
    )


@router.get("/", response_model=list[DepartmentResponse])
def get_departments(db:Session = Depends(get_db), current_user=Depends(get_current_user)):
    return DepartmentService.get_departments(db)

@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(department_id: int, db:Session = Depends(get_db), current_user=Depends(get_current_user)):
    return DepartmentService.get_department_by_id(
        db,
        department_id
    )

@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(department_id: int, department: DepartmentUpdate, db:Session = Depends(get_db), current_user= Depends(require_roles("admin"))):
    return DepartmentService.update_department(
        db,
        department_id,
        department
    )

@router.delete("/{department_id}")
def delete_department(department_id: int, db:Session = Depends(get_db), current_user = Depends(require_roles("admin"))):
    return DepartmentService.delete_department(
        db,
        department_id
    )
