from __future__ import annotations
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from backend.models.compras import UserRole

class UserBase(BaseModel):
    username: str
    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True
    department_id: UUID | None = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    department_id: UUID | None = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID

class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    is_active: bool
