from sqlalchemy.orm import Session
from app.models.department import Department
from app.models.employee import Employee
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate
)
from fastapi import HTTPException
class DepartmentService:

    @staticmethod
    def create_department(db: Session, department: DepartmentCreate, current_user: Employee):
        
        existing_department = (
            db.query(Department)
            .filter(
                Department.name == department.name,
                Department.organization_id == current_user.organization_id,
            )
            .first()
        )

        if existing_department:
            raise HTTPException(
                status_code = 409,
                detail="Department Already Exists"
            )
        
        new_department = Department(
            **department.model_dump(),
            organization_id=current_user.organization_id
        )

        db.add(new_department)
        db.commit()
        db.refresh(new_department)

        return new_department


    @staticmethod
    def get_departments(db:Session, current_user: Employee):
        departments = (
            db.query(Department)
            .filter(Department.is_active.is_(True), Department.organization_id == current_user.organization_id)
            .order_by(Department.name)
            .all()
        )
        return departments


    @staticmethod
    def get_department_by_id(db:Session, department_id: int, current_user: Employee):
        department = (
            db.query(Department)
            .filter(
                Department.id == department_id,
                Department.is_active.is_(True),
                Department.organization_id == current_user.organization_id
            )
            .first()
        )

        if department is None:
            raise HTTPException(
                status_code=404,
                detail="Department Not Found"
            )
        return department

    @staticmethod
    def update_department(db:Session, department_id: int, department: DepartmentUpdate, current_user: Employee):
        
        existing_department = DepartmentService.get_department_by_id(
            db,
            department_id,
            current_user
        )

        update_data = department.model_dump(
            exclude_unset=True
        )

        if "name" in update_data:
            duplicate = (
                db.query(Department)
                .filter(
                    Department.name == update_data["name"],
                    Department.id != department_id,
                    Department.is_active.is_(True),
                    Department.organization_id == current_user.organization_id  
                ).first()
                )
            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail="Department already exists"
                )
                
        for key, value in update_data.items():
            setattr(existing_department, key, value)

        db.commit()
        db.refresh(existing_department)

        return existing_department

    @staticmethod
    def delete_department(db:Session, department_id: int, current_user: Employee):
        
        department = DepartmentService.get_department_by_id(
            db,
            department_id,
            current_user
        )

        department.is_active = False

        db.commit()
        
        return {
            "message": "Department deleted successfully"
        }

    @staticmethod
    def get_department_employees(
        db: Session,
        department_id: int,
        current_user: Employee
    ):
        department = DepartmentService.get_department_by_id(
            db,
            department_id,
            current_user
        )

        employees = (
            db.query(Employee)
            .filter(
                Employee.department_id == department_id,
                Employee.is_active.is_(True),
                Employee.organization_id == current_user.organization_id
            )
            .all()
        )

        return {
            "id": department.id,
            "name": department.name,
            "employees": employees
        }