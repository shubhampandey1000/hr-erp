from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.employee import Employee
from app.schemas.auth import Token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    employee = (
        db.query(Employee)
        .filter(Employee.email == form_data.username)
        .first()
    )

    if not employee or not verify_password(form_data.password, employee.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_terminated = getattr(employee, "employment_status", None) in ["terminated", "resigned"]
    if not employee.is_active or is_terminated:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",  # Uniform response prevents enumeration
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": employee.email})

    return {"access_token": access_token, "token_type": "bearer"}