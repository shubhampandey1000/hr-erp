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
    is_active: str | None = None


class DepartmentResponse(DepartmentBase):
    id: int
    is_active = bool
    created_at = datetime
    updated_at = datetime

    model_config = ConfigDict(form_attribute = True)

    