from pydantic import BaseModel, ConfigDict
from pydantic import EmailStr


class DepartmentBasic(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
    
class EmployeeBasic(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    designation: str | None = None
    employee_code: str


    model_config = ConfigDict(from_attributes=True)