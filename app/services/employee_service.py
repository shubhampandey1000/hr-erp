from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, asc, desc
from app.models.employee import Employee
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate 
)
import random
import string
from app.core.security import hash_password
from app.models.enums import RoleEnum, EmploymentStatusEnum
from app.models.department import Department
from datetime import date

class EmployeeService:

    @staticmethod
    def _validate_manager_assignment(
        db:Session,
        employee_id: int | None,
        manager_id: int | None,
        organization_id: int,
    )-> None:
        """
        Validates manager assignment:
        - Manager must exist and be active
        - An employee cannot report to themselves
        - Prevents circular reporting chains (A -> B -> A)
        """
        if manager_id is None:
            return 

        if manager_id is not None and manager_id == employee_id:
            raise HTTPException(
                status_code=400,
                detail="An employee cannot be their own manager."
            )

        manager = (
            db.query(Employee)
            .filter(Employee.id == manager_id, Employee.is_active.is_(True), Employee.organization_id == organization_id,)
            .first()
        )

        if not manager:
            raise HTTPException(
                status_code=404,
                detail="Assigned manager not found or is inactive."
            )

        if employee_id is not None:
            current_ancestor_id = manager.manager_id
            visited = {employee_id, manager_id}

            while current_ancestor_id is not None:
                if current_ancestor_id == employee_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Circular reporting hierarchy detected. This assignment is not allowed."
                    )
                if current_ancestor_id in visited:
                    break
                visited.add(current_ancestor_id)
                ancestor = (
                    db.query(Employee.manager_id)
                    .filter(Employee.id == current_ancestor_id)
                    .first()
                )
                current_ancestor_id = ancestor[0] if ancestor else None

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
    def create_employee(db: Session, employee: EmployeeCreate, current_user: Employee)->Employee:
        existing_employee = (
            db.query(Employee)
            .filter(
                Employee.email == employee.email,
                Employee.is_active == True,
                Employee.organization_id == current_user.organization_id
                )
            .first()
        )
        if existing_employee:
            raise HTTPException(status_code=409, detail="Email already registered")

        employee_data = employee.model_dump(exclude={"password"})

        if current_user.role != RoleEnum.admin.value and current_user.role != RoleEnum.admin:
            employee_data["role"] = RoleEnum.employee.value
        elif isinstance(employee_data.get("role"), RoleEnum):
            employee_data["role"] = employee_data["role"].value

        if employee.department_id is not None:
            department = (
                db.query(Department)
                .filter(
                    Department.id == employee.department_id,
                    Department.is_active == True,
                    Department.organization_id == current_user.organization_id,
                )
                .first()
            )

            if department is None:
                raise HTTPException(
                    status_code=404,
                    detail="Department not found"
                )

        if employee.manager_id is not None:
            EmployeeService._validate_manager_assignment(db, employee_id=None, manager_id=employee.manager_id, organization_id=current_user.organization_id)
            
        if employee_data.get("employee_code"):
            duplicate_code = (
                db.query(Employee)
                .filter(
                    Employee.employee_code == employee_data["employee_code"],
                    Employee.is_active == True,
                    Employee.organization_id == current_user.organization_id
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

        db_employee = Employee(**employee_data, organization_id=current_user.organization_id)
        db.add(db_employee)
        db.commit()
        db.refresh(db_employee)
        return db_employee


    @staticmethod
    def get_employees(
        db: Session,
        search: str | None = None,
        department_id: int | None = None,
        role: RoleEnum | None = None,
        manager_id: int | None = None,
        employment_status: EmploymentStatusEnum | None = None,
        sort_by: str = "id",
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 10,
        current_user: Employee | None = None,
        ) -> dict:

        query = (
            db.query(Employee)
            .options(joinedload(Employee.department),
                     joinedload(Employee.manager)
            )
            .filter(Employee.is_active.is_(True), Employee.organization_id == current_user.organization_id)
        )

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Employee.first_name.ilike(search_pattern),
                    Employee.last_name.ilike(search_pattern),
                    Employee.email.ilike(search_pattern),
                    Employee.employee_code.ilike(search_pattern)
                )
            )

        if department_id is not None:
            department = (
                db.query(Department)
                .filter(
                    Department.id == department_id,
                    Department.is_active.is_(True),
                    Department.organization_id == current_user.organization_id
                )
                .first()
            )
            if not department:
                raise HTTPException(
                    status_code= 404,
                    detail="Department not found"
                )
            query = query.filter(
                            Employee.department_id == department_id,
                        )

        if role is not None:
            role_value = role.value if isinstance(role, RoleEnum) else role
            query = query.filter(
                Employee.role == role_value,
                Employee.organization_id == current_user.organization_id
            )
        if manager_id is not None:
            query = query.filter(Employee.manager_id == manager_id, Employee.organization_id == current_user.organization_id)

        if employment_status is not None:
            status_value = employment_status.value if isinstance(employment_status, EmploymentStatusEnum) else employment_status
            query = query.filter(Employee.employment_status == status_value, Employee.organization_id == current_user.organization_id)
 

        allowed_sort_fields = {
            "id": Employee.id,
            "first_name": Employee.first_name,
            "last_name": Employee.last_name,
            "email": Employee.email,
            "employee_code": Employee.employee_code,
            "date_of_joining": Employee.date_of_joining,
            "employment_status": Employee.employment_status,
            "created_at": Employee.created_at,
            
        }

        if sort_by not in allowed_sort_fields:
            raise HTTPException(
                status_code= 400,
                detail = f"Invalid Sort Field. Allowed fields: {', '.join(allowed_sort_fields.keys())}"
            )

        sort_column = allowed_sort_fields[sort_by]

        if sort_order == "asc":
            query = query.order_by(asc(sort_column))
        elif sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            raise HTTPException(
                status_code = 400,
                detail = "sort_order must be 'asc' or 'desc'"
            )

        total = query.count()
        items = query.offset(skip).limit(limit).all()

        return {
           "total": total,
            "skip": skip,
            "limit": limit,
            "items": items
        }
        
        


    @staticmethod
    def get_employee_by_id(db:Session, employee_id: int, current_user: Employee) -> Employee:
        
        employee = (
            db.query(Employee)
            .options(joinedload(Employee.department),
                     joinedload(Employee.manager))
            .filter(
                Employee.id == employee_id,
                Employee.is_active == True,
                Employee.organization_id == current_user.organization_id
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
    def update_employee(db:Session, employee_id: int, employee: EmployeeUpdate, current_user: Employee)-> Employee:
        
        existing_employee = EmployeeService.get_employee_by_id(
            db,
            employee_id,
            current_user
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
                    Department.is_active == True,
                    Department.organization_id == current_user.organization_id
                )
                .first()
            )
            if department is None:
                raise HTTPException(
                    status_code=404,
                    detail="Department not found"
                )
        if "manager_id" in update_data:
            EmployeeService._validate_manager_assignment(
                db,
                employee_id=employee_id,
                manager_id=update_data["manager_id"],
                organization_id=current_user.organization_id
            )

        if "email" in update_data:
            duplicate = (
                db.query(Employee)
                .filter(
                    Employee.email == update_data["email"],
                    Employee.id != employee_id,
                    Employee.is_active == True,
                    Employee.organization_id == existing_employee.organization_id,
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
                    Employee.is_active == True,
                    Employee.organization_id == existing_employee.organization_id,
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

        if "employment_status" in update_data:
            status_val = update_data["employment_status"]
            if isinstance(status_val, EmploymentStatusEnum):
                update_data["employment_status"] = status_val.value

            # Auto-set termination date if marked terminated without explicit date
            if update_data["employment_status"] == EmploymentStatusEnum.terminated.value:
                if not update_data.get("termination_date") and not existing_employee.termination_date:
                    update_data["termination_date"] = date.today()

        for key, value in update_data.items():
            setattr(existing_employee, key, value)

        db.commit()
        db.refresh(existing_employee)

        return existing_employee    
    

    @staticmethod
    def delete_employee(db: Session, employee_id: int, current_user: Employee)-> dict:

        employee = EmployeeService.get_employee_by_id(
            db,
            employee_id,
            current_user
        )

        employee.is_active = False
        employee.employment_status = EmploymentStatusEnum.terminated.value
        if not employee.termination_date:
            employee.termination_date = date.today()

        db.commit()

        return {
            "message": "Employee deactivated successfully"
        }
    

    @staticmethod
    def update_role(
        db: Session,
        employee_id: int,
        role: RoleEnum,
        current_user: Employee
    )-> Employee:
        employee = EmployeeService.get_employee_by_id(
            db,
            employee_id,
            current_user
        )

        employee.role = (
            role.value
            if isinstance(role, RoleEnum)
            else role
        )

        db.commit()
        db.refresh(employee)

        return employee

    @staticmethod
    def get_direct_reports(db: Session, employee_id: int, current_user: Employee) -> list[Employee]:
        # Ensure manager exists and is active
        EmployeeService.get_employee_by_id(db, employee_id, current_user)
        
        return (
            db.query(Employee)
            .filter(
                Employee.manager_id == employee_id,
                Employee.is_active.is_(True),
                Employee.organization_id == current_user.organization_id
            )
            .order_by(Employee.first_name.asc())
            .all()
        )

    @staticmethod
    def reactivate_employee(db: Session, employee_id: int, current_user: Employee) -> Employee:
        # Query without is_active filter to find deactivated records
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.organization_id == current_user.organization_id).first()
        
        if not employee:
            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )
            
        if employee.is_active:
            raise HTTPException(
                status_code=400,
                detail="Employee is already active"
            )

        # Check for unique index conflicts before reactivating
        email_conflict = (
            db.query(Employee)
            .filter(
                Employee.email == employee.email,
                Employee.is_active.is_(True),
                Employee.id != employee_id,
                Employee.organization_id == current_user.organization_id
            )
            .first()
        )
        if email_conflict:
            raise HTTPException(
                status_code=409,
                detail="Cannot reactivate: email is currently in use by another active employee"
            )

        code_conflict = (
            db.query(Employee)
            .filter(
                Employee.employee_code == employee.employee_code,
                Employee.is_active.is_(True),
                Employee.id != employee_id,
                Employee.organization_id == current_user.organization_id
            )
            .first()
        )
        if code_conflict:
            raise HTTPException(
                status_code=409,
                detail="Cannot reactivate: employee code is currently in use by another active employee"
            )

        employee.is_active = True
        employee.employment_status = EmploymentStatusEnum.active.value
        employee.termination_date = None

        db.commit()
        db.refresh(employee)
        return employee