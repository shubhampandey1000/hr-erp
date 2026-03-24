from pydantic import BaseModel, EmailStr
from datetime import date

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    department: str | None = None
    designation: str | None = None
    date_of_joining: date | None = None 


class EmployeeCreate(EmployeeBase):
    password:str    


class EmployeeResponse(EmployeeBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True
        