from pydantic import BaseModel, ConfigDict, Field
from pydantic import EmailStr
from typing import Generic, TypeVar, List

T = TypeVar("T")

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

class PaginatedResponse(BaseModel, Generic[T]):
    total: int = Field(..., description="Total number of matching records")
    skip: int = Field(..., description="Number of skipped records")
    limit: int = Field(..., description="Max records returned per page")
    items: List[T] = Field(..., description="List of items for the current page")

class ManagerBasic(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    employee_code: str
    designation: str | None = None

    model_config = ConfigDict(from_attributes=True)