from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import DepartmentBasic, EmployeeBasic


class DepartmentBase(BaseModel):

    name: str
    description: str | None = None


class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid")

class DepartmentResponse(DepartmentBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes = True)



class DepartmentEmployeeResponse(DepartmentBasic):
    employees: list[EmployeeBasic]

    model_config = ConfigDict(from_attributes=True)

    