import enum

class RoleEnum(str, enum.Enum):
    admin = "admin"
    hr = "hr"
    manager = "manager"
    employee = "employee"   

class EmploymentStatusEnum(str, enum.Enum):
    active = "active"
    on_leave = "on_leave"
    terminated = "terminated"
    