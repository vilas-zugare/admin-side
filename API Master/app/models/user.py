from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    commands = relationship("Command", back_populates="owner", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="owner", cascade="all, delete-orphan")
    app_logs = relationship("AppLog", back_populates="owner", cascade="all, delete-orphan")
    browser_logs = relationship("BrowserLog", back_populates="owner", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    device_hw_id = Column(String, unique=True, index=True, nullable=False) # Hardware UUID
    name = Column(String, nullable=True) # e.g. "Dell Latitude"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="devices")
