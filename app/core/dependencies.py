from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.employee import Employee

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        email: str = payload.get("sub")

        if email is None:
            raise HTTPException(status_code = 401, detail = "Invalid Token")
        
    except JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid Token")
    

    user = db.query(Employee).filter(Employee.email == email).first()

    if user is None:
        raise HTTPException(status_code = 401, detail = "User Not Found")
    
    return user


def require_roles(*roles):
    def checker(current_user: Employee = Depends(get_current_user)):
            if current_user.role not in roles:
                raise HTTPException(
                status_code=403,
                detail="Not enough permissions"
            )
            return current_user
    return checker 