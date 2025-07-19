import re
from datetime import datetime, date
from typing import Optional

from pydantic import validator, EmailStr
from pydantic.v1 import BaseModel, constr


class UserSchema(BaseModel):
    id: int
    email: constr(max_length=255)
    hashed_password: constr(max_length=255)
    is_active: bool
    created_at: datetime
    updated_at: datetime
    group_id: int

    class Config:
        orm_mode = True


class UserProfileSchema(BaseModel):
    id: int
    user_id: int
    first_name: Optional[constr(max_length=100)] = None
    last_name: Optional[constr(max_length=100)] = None
    avatar: Optional[constr(max_length=255)] = None
    gender: Optional[constr(max_length=10)] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    class Config:
        orm_mode = True


class RefreshTokenSchema(BaseModel):
    id: int
    user_id: int
    token: constr(max_length=255)
    expires_at: datetime


class PasswordResetTokenSchema(BaseModel):
    id: int
    user_id: int
    token: constr(max_length=255)
    expires_at: datetime


class ActivationTokenSchema(BaseModel):
    id: int
    user_id: int
    token: constr(max_length=255)
    expires_at: datetime


class UserGroupSchema(BaseModel):
    id: int
    name: constr(max_length=50)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8 or not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v) \
                or not re.search(r"[0-9]", v) or not re.search(r"[!@#$%^&*]", v):
            raise ValueError("Password must be at least 8 characters long, contain at least one uppercase, ")
        return v


class RegisterResponse(BaseModel):
    email: EmailStr
    message: str


class ResendActivationEmailRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class PasswordResetToken(BaseModel):
    user_id: int
    token: str
    expires_at: datetime