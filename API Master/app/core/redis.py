import redis
import redis.asyncio as async_redis
from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
    socket_timeout=2,
    socket_connect_timeout=2,
    retry_on_timeout=True
)

async_redis_client = async_redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    socket_timeout=2,
    socket_connect_timeout=2
)

def get_redis():
    """Provides a thread-safe Redis client."""
    return redis_client

def get_async_redis():
    """Provides an async Redis client."""
    return async_redis_client
