import os
import redis
import redis.asyncio as async_redis
from app.core.config import settings

REDIS_URL = os.getenv("REDIS_URL", f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=2,
    socket_connect_timeout=2,
    retry_on_timeout=True
)

async_redis_client = async_redis.from_url(
    REDIS_URL,
    socket_timeout=2,
    socket_connect_timeout=2
)

def get_redis():
    """Provides a thread-safe Redis client."""
    return redis_client

def get_async_redis():
    """Provides an async Redis client."""
    return async_redis_client
