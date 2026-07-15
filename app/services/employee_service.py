from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.employee import Employee
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate 
)
import random
import string
from app.core.security import hash_password
from app.models.enums import RoleEnum
from app.models.department import Department

class EmployeeService:

    @staticmethod
    def generate_employee_code(db: Session) -> str:
        for _ in range(10):
            code = "EMP" + "".join(random.choices(string.digits, k=8))

            existing = (
                db.query(Employee)
                .filter(Employee.employee_code == code)
                .first()
            )

            if not existing:
                return code
        raise HTTPException(
            status_code=500,
            detail="Unable to generate unique employee code"
        )

    @staticmethod
    def create_employee(db: Session, employee: EmployeeCreate, current_user: Employee):
        existing_employee = (
            db.query(Employee)
            .filter(
                Employee.email == employee.email,
                Employee.is_active == True
                )
            .first()
        )
        if existing_employee:
            raise HTTPException(status_code=409, detail="Email already registered")

        employee_data = employee.model_dump(exclude={"password"})
        if current_user.role != RoleEnum.admin:
            employee_data["role"] = RoleEnum.employee.value

        if employee.department_id is not None:
            department = (
                db.query(Department)
                .filter(
                    Department.id == employee.department_id,
                    Department.is_active == True
                )
                .first()
            )

            if department is None:
                raise HTTPException(
                    status_code=404,
                    detail="Department not found"
                )

        if employee_data.get("employee_code"):
            duplicate_code = (
                db.query(Employee)
                .filter(
                    Employee.employee_code == employee_data["employee_code"],
                    Employee.is_active == True
                    )
                .first()
                )
            if duplicate_code:
                raise HTTPException(
                    status_code=409,
                    detail="Employee code already exists"
                )
        else:
            employee_data["employee_code"] = EmployeeService.generate_employee_code(db)

        employee_data["hashed_password"] = hash_password(employee.password)
        if isinstance(employee_data.get("role"), RoleEnum):
            employee_data["role"] = employee_data["role"].value

        db_employee = Employee(**employee_data)
        db.add(db_employee)
        db.commit()
        db.refresh(db_employee)
        return db_employee


    @staticmethod
    def get_employees(db: Session):
        
        employees = (
            db.query(Employee)
            .filter(Employee.is_active == True)
            .all()
        )

        return employees


    @staticmethod
    def get_employee_by_id(db:Session, employee_id: int):
        
        employee = (
            db.query(Employee)
            .filter(
                Employee.id == employee_id,
                Employee.is_active == True
            )
            .first()
        )

        if employee is None:
            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )
        
        return employee

    @staticmethod
    def update_employee(db:Session, employee_id: int, employee: EmployeeUpdate):
        
        existing_employee = EmployeeService.get_employee_by_id(
            db,
            employee_id
        )

        update_data = employee.model_dump(exclude_unset=True)

        if (
            "department_id" in update_data
            and update_data["department_id"] is not None
            ):
            department = (
                db.query(Department)
                .filter(
                    Department.id == update_data["department_id"],
                    Department.is_active == True
                )
                .first()
            )

            if department is None:
                raise HTTPException(
                    status_code=404,
                    detail="Department not found"
                )

        if "email" in update_data:
            duplicate = (
                db.query(Employee)
                .filter(
                    Employee.email == update_data["email"],
                    Employee.id != employee_id,
                    Employee.is_active == True
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail="Email already registered"
                )
            
        if "employee_code" in update_data:
            duplicate = (
                db.query(Employee)
                .filter(
                    Employee.employee_code == update_data["employee_code"],
                    Employee.id != employee_id,
                    Employee.is_active == True
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail="Employee Code Already Exists"
                )
            
        if "password" in update_data:
            update_data["hashed_password"] = hash_password(
                update_data.pop("password")
            )

        if(
            "role" in update_data
            and isinstance(update_data["role"], RoleEnum)
        ):
            update_data["role"] = update_data["role"].value

        for key, value in update_data.items():
            setattr(existing_employee, key, value)

        db.commit()
        db.refresh(existing_employee)

        return existing_employee    
    

    @staticmethod
    def delete_employee(db: Session, employee_id: int):

        employee = EmployeeService.get_employee_by_id(
            db,
            employee_id
        )

        employee.is_active = False

        db.commit()

        return {
            "message": "Employee deactivated successfully"
        }
    

    @staticmethod
    def update_role(
        db: Session,
        employee_id: int,
        role: RoleEnum
    ):
        employee = EmployeeService.get_employee_by_id(
            db,
            employee_id
        )

        employee.role = (
            role.value
            if isinstance(role, RoleEnum)
            else role
        )

        db.commit()
        db.refresh(employee)

        return employee