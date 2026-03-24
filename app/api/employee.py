from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeResponse
from app.core.security import hash_password
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/employees", tags=["Employees"])

@router.post("/", response_model = EmployeeResponse)
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing_employee = db.query(Employee).filter(Employee.email == employee.email).first()

    if existing_employee:
        raise HTTPException(status_code = 400, detail = "Email Already Registered")

    db_employee = Employee(**employee.model_dump(exclude={"password"}), password=hash_password(employee.password))
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.get("/", response_model = list[EmployeeResponse])
def get_employees(db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return db.query(Employee).filter(Employee.is_active == True).all()


@router.put("/{employee_id}", response_model = EmployeeResponse)
def update_employee(employee_id: int, update_data: EmployeeCreate, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail = "Employee not Found")
    
    existing_email = db.query(Employee).filter(Employee.email == update_data.email, Employee.id != employee_id).first()

    if existing_email:
        raise HTTPException(status_code = 400, detail = "Email Already Registered")
    

    update_dict = update_data.model_dump()

    if "password" in update_dict and update_dict["password"]:
        update_dict["password"] = hash_password(update_dict["password"])

    for key, value in update_dict().items():
        setattr(employee, key, value)

    db.commit()
    db.refresh(employee)

    return employee

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code = 400, detail="Employee Not Found")
    
    return employee

@router.delete("/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code = 404, detail = "Employee Not Found")
    
    employee.is_active = False

    db.commit()
    return {"message": "Employee Deavtivated Successfully"}

