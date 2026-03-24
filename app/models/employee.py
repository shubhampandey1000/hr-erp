from sqlalchemy import Column, Integer, String, Date, Boolean
from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    department = Column(String(100))
    designation = Column(String(100))
    date_of_joining = Column(Date)
    is_active = Column(Boolean, default=True)
    password = Column(String, nullable = False)
    role = Column(String, default="employee")
