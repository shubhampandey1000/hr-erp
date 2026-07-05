from pydantic import BaseModel, ConfigDict
from datetime import datetime

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

class DepartmentBasic(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)