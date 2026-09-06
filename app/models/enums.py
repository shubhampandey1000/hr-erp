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

class LeaveStatusEnum(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"

class AttendanceStatusEnum(str, enum.Enum):
    present = "present"
    half_day = "half_day"
    absent = "absent"
    on_leave = "on_leave"
    weekend_work = "weekend_work"

class CompOffStatusEnum(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

    

    