from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


# Alias for backward/alternative compatibility
TokenResponse = Token


class TokenData(BaseModel):
    email: str | None = None
    role: str | None = None