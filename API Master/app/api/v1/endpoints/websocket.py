from typing import Dict, List, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status, Depends
from jose import jwt, JWTError
from app.core.config import settings
from app.core.redis import get_async_redis
from app.api.deps import get_db
from app.models.user import User
from sqlalchemy.orm import Session
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

# --- WebRTC Signaling State ---
# THE PURPOSE: This dictionary tracks active WebRTC connections grouped by room_id (user ID) ON THIS SPECIFIC WORKER.
# THE REPLACEMENT: Formerly `rooms`. Renamed to `local_rooms` to clarify that this state is local to the Uvicorn worker instance.
class RoomState:
    def __init__(self):
        self.host: Optional[WebSocket] = None
        self.viewers: Set[WebSocket] = set()
        self.latest_offer: Optional[dict] = None

local_rooms: Dict[str, RoomState] = {}
admin_viewers: Set[WebSocket] = set()

async def _webrtc_redis_listener():
    """
    Background multiplexer task. Listens to ALL WebRTC rooms via psubscribe and admin_events via subscribe.
    """
    redis = get_async_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("webrtc_room_*")
    await pubsub.subscribe("admin_events")
    logger.info("Global Redis Multiplexer started across workers.")
    try:
        async for message in pubsub.listen():
            if message['type'] == 'pmessage':
                channel = message['channel'].decode('utf-8')
                room_id = channel.replace("webrtc_room_", "")
                
                if room_id in local_rooms:
                    try:
                        data_str = message['data'].decode('utf-8')
                        payload = json.loads(data_str)
                        sender_id = payload.pop("_sender", None)
                        
                        room = local_rooms[room_id]
                        
                        # Cache the offer so if the host connects a few seconds later, they still get it
                        if payload.get("type") == "offer":
                            room.latest_offer = payload
                            
                        targets = set(room.viewers)
                        if room.host:
                            targets.add(room.host)
                            
                        for client in targets:
                            # Do not echo the message back to the sender
                            if str(id(client)) != sender_id:
                                try:
                                    await client.send_text(json.dumps(payload))
                                except Exception as e:
                                    logger.error(f"Error broadcasting to client in room {room_id}: {e}")
                    except Exception as e:
                        logger.error(f"Error processing multiplexed WebRTC message: {e}")
            elif message['type'] == 'message' and message['channel'].decode('utf-8') == "admin_events":
                try:
                    data_str = message['data'].decode('utf-8')
                    logger.debug(f"Event received in multiplexer: {data_str}")
                    for client in list(admin_viewers):
                        try:
                            await client.send_text(data_str)
                        except Exception as e:
                            logger.error(f"Error broadcasting to admin viewer: {e}")
                except Exception as e:
                    logger.error(f"Error processing multiplexed Admin Event message: {e}")
    finally:
        await pubsub.close()

listener_task = None

def start_webrtc_listener():
    global listener_task
    listener_task = asyncio.create_task(_webrtc_redis_listener())

def stop_webrtc_listener():
    if listener_task:
        listener_task.cancel()

# THE PURPOSE: This is the new WebRTC signaling endpoint. It accepts both the admin (viewer) and the desktop agent (host). Its only job is to pass SDP offers and ICE candidates between them so they can connect directly.
# THE REPLACEMENT: Replaced the old `/live` and `/admin/{target_user_id}` endpoints which used to handle raw video frames. They were removed to save server bandwidth.
@router.websocket("/ws")
async def websocket_signaling_endpoint(
    websocket: WebSocket,
    role: str = Query(..., description="Role of the connection: 'host' or 'viewer'"),
    room_id: str = Query(..., description="Target user ID creating the room"),
    token: str = Query(..., description="JWT Bearer token")
):
    """
    WebRTC P2P Signaling Endpoint.
    URL: ws://HOST/api/v1/ws/ws?role={host|viewer}&room_id={user_id}&token={token}
    """
    db = next(get_db())
    try:
        user = get_user_from_token(token, db)
    finally:
        db.close()

    if not user:
        logger.warning(f"Signaling WS denied: Invalid or expired token")
        await websocket.accept()
        await websocket.close(code=4001)
        return

    # For the viewer role, ensure they are an admin.
    if role == "viewer" and not user.is_superuser:
        logger.warning(f"Signaling WS denied: Viewer role requires superuser")
        await websocket.accept()
        await websocket.close(code=4001)
        return

    await websocket.accept()
    
    if room_id not in local_rooms:
        local_rooms[room_id] = RoomState()
        
    room = local_rooms[room_id]
    
    if role == "host":
        # Kick zombie host if a new one connects
        if room.host and room.host != websocket:
            try:
                await room.host.close(code=status.WS_1000_NORMAL_CLOSURE)
            except Exception:
                pass
        room.host = websocket
        
        # Deliver the cached offer if the viewer connected first
        if room.latest_offer:
            try:
                await websocket.send_text(json.dumps(room.latest_offer))
            except Exception:
                pass
    else:
        room.viewers.add(websocket)
    
    logger.info(f"Signaling connected: role={role}, room_id={room_id}")
    
    try:
        redis = get_async_redis()
        while True:
            # Read incoming JSON messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                # Publish offer, answer, or ice_candidate to the REDIS MULTIPLEXER instead of direct local broadcast
                msg_type = message.get("type", "")
                if msg_type in ["offer", "answer", "ice_candidate"]:
                    # Tag with sender_id so the multiplexer knows not to echo it back
                    message["_sender"] = str(id(websocket))
                    await redis.publish(f"webrtc_room_{room_id}", json.dumps(message))
                else:
                    logger.debug(f"Received unknown message type '{msg_type}' in room {room_id}")
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received on signaling websocket: {data}")
    except WebSocketDisconnect:
        logger.info(f"Signaling disconnected: role={role}, room_id={room_id}")
    except Exception as e:
        logger.error(f"Signaling connection error for room_id {room_id}: {e}")
    finally:
        # Cleanup connection
        if room_id in local_rooms:
            r = local_rooms[room_id]
            if role == "host" and r.host == websocket:
                r.host = None
                r.latest_offer = None
            elif role == "viewer" and websocket in r.viewers:
                r.viewers.remove(websocket)
                
            if not r.host and not r.viewers:
                del local_rooms[room_id]

def get_user_from_token(token: str, db: Session) -> Optional[User]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except JWTError:
        return None

@router.websocket("/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Global Admin Events Endpoint.
    URL: ws://HOST/api/v1/ws/events?token=JWT
    """
    logger.info(f"Admin Events connection attempt triggered. Token provided: {'Yes' if token else 'No'}")
    if not token:
        logger.warning("No token provided for Admin Events WebSocket")
        await websocket.accept()
        await websocket.close(code=4001)
        return

    db = next(get_db())
    try:
        admin_user = get_user_from_token(token, db)
    finally:
        db.close()
    
    if not admin_user or not admin_user.is_superuser:
        logger.warning(f"Unauthorized admin access attempt to events. Admin user: {admin_user.id if admin_user else 'None'}")
        await websocket.accept()
        await websocket.close(code=4001)
        return

    logger.info(f"Admin {admin_user.id} authorized for events. Accepting connection...")
    await websocket.accept()
    
    admin_viewers.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Admin {admin_user.id} disconnected from events")
    finally:
        admin_viewers.discard(websocket)
