from typing import Optional, List
from pydantic import BaseModel, EmailStr
import uuid

# Shared properties
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str
    device_id: str
    device_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    device_id: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    id: str
    is_active: bool
    is_superuser: bool
    
    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class DeviceBase(BaseModel):
    device_hw_id: str
    name: Optional[str] = None

class DeviceCreate(DeviceBase):
    pass

class Device(DeviceBase):
    id: str
    user_id: str
    last_seen: Optional[str] = None
    
    class Config:
        from_attributes = True
