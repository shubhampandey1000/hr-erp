from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.employee import Employee

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Employee:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid Token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(Employee).filter(Employee.email == email).first()

    if user is None:
        raise credentials_exception

    is_terminated = getattr(user, "employment_status", None) in ["terminated", "resigned"]
    if not user.is_active or is_terminated:
        raise credentials_exception

    return user


def require_roles(*roles):
    def checker(current_user: Employee = Depends(get_current_user)) -> Employee:
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        allowed_roles = [r.value if hasattr(r, "value") else str(r) for r in roles]

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions"
            )
        return current_user

    return checker
