from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Simple logging for HTTP only
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "UNKNOWN")
        logger.info(f"REQ: {method} {path}")

        await self.app(scope, receive, send)
