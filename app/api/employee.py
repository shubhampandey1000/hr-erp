import random
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.core.security import hash_password
from app.core.dependencies import require_roles
from app.models.enums import RoleEnum

router = APIRouter(prefix="/employees", tags=["Employees"])


def generate_employee_code(db: Session) -> str:
    for _ in range(10):
        code = "EMP" + "".join(random.choices(string.digits, k=8))
        existing = db.query(Employee).filter(Employee.employee_code == code).first()
        if not existing:
            return code
    raise HTTPException(status_code=500, detail="Unable to generate unique employee code")


@router.post("/", response_model=EmployeeResponse)
def create_employee(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin, RoleEnum.hr)),
):
    existing_employee = db.query(Employee).filter(Employee.email == employee.email).first()
    if existing_employee:
        raise HTTPException(status_code=400, detail="Email already registered")

    employee_data = employee.model_dump(exclude={"password"})
    if current_user.role != RoleEnum.admin:
        employee_data["role"] = RoleEnum.employee.value

    if employee_data.get("employee_code"):
        duplicate_code = db.query(Employee).filter(Employee.employee_code == employee_data["employee_code"]).first()
        if duplicate_code:
            raise HTTPException(status_code=400, detail="Employee code already exists")
    else:
        employee_data["employee_code"] = generate_employee_code(db)

    employee_data["hashed_password"] = hash_password(employee.password)
    if isinstance(employee_data.get("role"), RoleEnum):
        employee_data["role"] = employee_data["role"].value

    db_employee = Employee(**employee_data)
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee


@router.get("/", response_model=list[EmployeeResponse])
def get_employees(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    return db.query(Employee).filter(Employee.is_active == True).all()


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    update_data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    if "email" in update_dict and update_dict["email"]:
        existing_email = (
            db.query(Employee)
            .filter(Employee.email == update_dict["email"], Employee.id != employee_id)
            .first()
        )
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")

    if "employee_code" in update_dict and update_dict["employee_code"]:
        existing_code = (
            db.query(Employee)
            .filter(Employee.employee_code == update_dict["employee_code"], Employee.id != employee_id)
            .first()
        )
        if existing_code:
            raise HTTPException(status_code=400, detail="Employee code already exists")

    if "password" in update_dict and update_dict["password"]:
        update_dict["hashed_password"] = hash_password(update_dict.pop("password"))

    if "role" in update_dict and isinstance(update_dict.get("role"), RoleEnum):
        update_dict["role"] = update_dict["role"].value

    for key, value in update_dict.items():
        setattr(employee, key, value)

    db.commit()
    db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.is_active = False
    db.commit()
    return {"message": "Employee deactivated successfully"}


@router.put("/{employee_id}/role")
def update_role(
    employee_id: int,
    role: RoleEnum,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(RoleEnum.admin)),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee.role = role.value if isinstance(role, RoleEnum) else role
    db.commit()
    db.refresh(employee)
    return employee
