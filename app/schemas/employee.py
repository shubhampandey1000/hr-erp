from datetime import date, datetime
from pydantic import BaseModel, EmailStr
from pydantic import ConfigDict
from app.models.enums import RoleEnum
from app.schemas.department import DepartmentBasic

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    department_id: int | None = None
    designation: str | None = None
    date_of_joining: date | None = None
    role: RoleEnum = RoleEnum.employee

class EmployeeCreate(EmployeeBase):
    password: str
    employee_code: str | None = None

class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    department_id: int | None = None
    designation: str | None = None
    date_of_joining: date | None = None
    password: str | None = None
    employee_code: str | None = None
    role: RoleEnum | None = None

class EmployeeResponse(EmployeeBase):
    id: int
    is_active: bool
    employee_code: str
    created_at: datetime
    updated_at: datetime
    department: DepartmentBasic | None = None

    model_config = ConfigDict(from_attributes=True)
        