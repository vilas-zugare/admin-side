from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class Command(Base):
    __tablename__ = "commands"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    command = Column(String, nullable=False) # TAKE_SCREENSHOT, etc.
    payload = Column(JSON, nullable=True)
    status = Column(String, default="PENDING") # PENDING, SENT, EXECUTED, FAILED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    executed_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="commands")
    screenshot = relationship("Screenshot", back_populates="command_rel", uselist=False)

class Screenshot(Base):
    __tablename__ = "screenshots"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    command_id = Column(String, ForeignKey("commands.id"), nullable=True)
    url = Column(String, nullable=False)
    file_path = Column(String, nullable=True) # Local path if stored locally
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="screenshots")
    command_rel = relationship("Command", back_populates="screenshot")

class AppLog(Base):
    __tablename__ = "app_logs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    command_id = Column(String, ForeignKey("commands.id"), nullable=True)
    apps = Column(JSON, nullable=False) # List of running apps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="app_logs")

class BrowserLog(Base):
    __tablename__ = "browser_logs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    command_id = Column(String, ForeignKey("commands.id"), nullable=True)
    browser = Column(String, nullable=True)
    youtube_open = Column(Boolean, default=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="browser_logs")
