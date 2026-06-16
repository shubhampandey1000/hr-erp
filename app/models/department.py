from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy import text
from sqlalchemy.orm import relationship

from app.core.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key = True, index = True)
    name = Column(String(200), unique = True, nullable = False)
    description = Column(String, nullable = True)
    is_active = Column(Boolean, nullable = False, default = True, server_default = text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable = False)
    updated_at = Column(DateTime(timezone = True), server_default=func.now(), nullable = False)
    employees = relationship("Employee", back_populates = "department")