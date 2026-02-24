from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.core.redis import get_redis
from app.models.data import Command, Screenshot, AppLog, BrowserLog
from app.schemas import client as client_schema
from app.models.user import User
import json
import base64
import os
import uuid
import logging
from datetime import datetime

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/heartbeat", response_model=client_schema.HeartbeatResponse)
def heartbeat(
    *,
    status_in: client_schema.HeartbeatRequest,
    current_user: User = Depends(deps.get_current_user),
    redis = Depends(get_redis)
) -> Any:
    # Diagnostic Log
    logger.info(f"HEARTBEAT_ENTERED for user: {current_user.id}")
    # Update Redis
    # PRD: online:{user_id} -> timestamp (TTL 30s)
    try:
        redis.setex(f"online:{current_user.id}", 30, "online")
    except Exception as e:
        logger.error(f"Redis connection failed during heartbeat: {e}")
        # We don't want to crash the whole heartbeat just because Redis is down
        # Online status in dashboard might be affected, but client can still function
    return {"success": True}

@router.get("/commands", response_model=List[client_schema.CommandSchema])
def get_commands(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    # Get PENDING commands
    commands = db.query(Command).filter(
        Command.user_id == current_user.id,
        Command.status == "PENDING"
    ).all()
    return commands

@router.post("/command/ack", response_model=dict)
def ack_command(
    ack_in: client_schema.CommandAck,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    cmd = db.query(Command).filter(Command.id == ack_in.command_id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")
    
    cmd.status = ack_in.status
    db.commit()
    return {"success": True}

@router.post("/screenshot/upload", response_model=client_schema.ScreenshotResponse)
def upload_screenshot(
    screenshot_in: client_schema.ScreenshotUpload,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    real_url = ""
    try:
        if screenshot_in.image_base64:
            # Instead of saving to disk, we store the base64 as a Data URL in the database
            real_url = f"data:image/png;base64,{screenshot_in.image_base64}"
        else:
             logger.warning("No image_base64 provided in upload")
             real_url = "https://placehold.co/600x400?text=No+Image"
    except Exception as e:
        logger.error(f"Error processing screenshot: {e}")
        real_url = "https://placehold.co/600x400?text=Error+Processing"
    
    shot = Screenshot(
        user_id=current_user.id,
        command_id=screenshot_in.command_id,
        url=real_url,
        file_path=None # No longer using filesystem
    )
    db.add(shot)
    db.commit()
    
    # Cleanup old auto-screenshots if this is an auto-screenshot
    if screenshot_in.is_auto:
        # Keep only the last 10 auto-screenshots (where command_id is None)
        old_screenshots = db.query(Screenshot).filter(
            Screenshot.user_id == current_user.id,
            Screenshot.command_id == None
        ).order_by(Screenshot.created_at.desc()).offset(10).all()
        
        for old_shot in old_screenshots:
            # We don't need os.remove anymore as there are no files
            db.delete(old_shot)
        
        if old_screenshots:
            db.commit()
    
    return {"success": True, "screenshot_url": real_url}

@router.post("/apps/upload", response_model=dict)
def upload_apps(
    apps_in: client_schema.AppLogUpload,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    log = AppLog(
        user_id=current_user.id,
        command_id=apps_in.command_id,
        apps=[app.dict() for app in apps_in.apps]
    )
    db.add(log)
    db.commit()
    return {"success": True}

@router.post("/browser/upload", response_model=dict)
def upload_browser(
    browser_in: client_schema.BrowserLogUpload,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    log = BrowserLog(
        user_id=current_user.id,
        command_id=browser_in.command_id,
        browser=browser_in.browser,
        youtube_open=browser_in.youtube_open,
        details=browser_in.details
    )
    db.add(log)
    db.commit()
    return {"success": True}
@router.post("/notification/reply", response_model=dict)
def notify_reply(
    reply_in: client_schema.NotificationReply,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    redis = Depends(get_redis)
) -> Any:
    cmd = db.query(Command).filter(Command.id == reply_in.command_id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")
    
    # Update command with reply
    if not cmd.payload:
        cmd.payload = {}
    
    # Store reply in payload
    updated_payload = dict(cmd.payload)
    updated_payload["reply"] = reply_in.message
    updated_payload["replied_at"] = datetime.now().isoformat()
    cmd.payload = updated_payload
    cmd.status = "REPLIED"
    
    db.commit()
    logger.info(f"Notification reply stored for command {cmd.id} from user {current_user.name}")

    # Publish to a global events channel for admins
    event_data = {
        "type": "NOTIFICATION_REPLY",
        "user_id": current_user.id,
        "user_name": current_user.name,
        "command_id": cmd.id,
        "message": reply_in.message
    }
    published = redis.publish("admin_events", json.dumps(event_data))
    logger.info(f"Published reply event to Redis 'admin_events'. Subscribers: {published}")
    
    return {"success": True}
