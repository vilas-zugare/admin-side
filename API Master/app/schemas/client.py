from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# Heartbeat
class HeartbeatRequest(BaseModel):
    status: str

class HeartbeatResponse(BaseModel):
    success: bool

# Command
class CommandCreate(BaseModel):
    user_id: str
    command: str
    payload: Optional[Dict[str, Any]] = {}

class CommandResponse(BaseModel):
    success: bool
    command_id: str

class CommandAck(BaseModel):
    command_id: str
    status: str

class CommandSchema(BaseModel):
    id: str
    command: str
    payload: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Data Uploads
class ScreenshotUpload(BaseModel):
    command_id: Optional[str]
    image_base64: str
    is_auto: Optional[bool] = False

class ScreenshotResponse(BaseModel):
    success: bool
    screenshot_url: str

class AppInfo(BaseModel):
    name: str
    pid: int
    title: Optional[str] = None
    exe_path: Optional[str] = None
    icon: Optional[str] = None
    duration: Optional[str] = None

class AppLogUpload(BaseModel):
    command_id: Optional[str]
    apps: List[AppInfo]

class BrowserLogUpload(BaseModel):
    command_id: Optional[str]
    browser: str
    youtube_open: bool
    details: Optional[Dict[str, Any]] = None

# Admin
class AdminUserList(BaseModel):
    users: List[Dict[str, Any]]

class NotifySchema(BaseModel):
    user_id: str
    title: str
    message: str

class NotificationReply(BaseModel):
    command_id: str
    message: str
