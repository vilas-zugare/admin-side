from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api import api_router
from app.core.database import engine, Base
from app.api.v1.endpoints import websocket
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create DB tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")
except Exception as e:
    logger.error(f"Failed to connect to the database: {e}")
    logger.error("CRITICAL: Please check your .env file. Ensure POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_SERVER are correct.")
    logger.error("Also ensure PostgreSQL service is running.")
    logger.error("Also ensure PostgreSQL service is running.")
    # Critical error but we allow startup to debugging purposes, 
    # though API endpoints requiring DB will fail.
    # We remove the 'pass' and just let it continue after logging.

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
from fastapi.staticfiles import StaticFiles
import os

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from app.middleware import LoggingMiddleware
app.add_middleware(LoggingMiddleware)

# Ensure static dir exists
os.makedirs("static/screenshots", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router, prefix=settings.API_V1_STR)

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    logger.error(f"GLOBAL ERROR: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": f"API_FIX_MARK_1: {str(exc)}"}
    )

@app.get("/")
def read_root():
    # Print all registered routes for debugging
    # for route in app.routes:
    #    logger.info(f"ROUTE: {route.path} (Name: {route.name})")
    return {"message": "Welcome to Windows Monitoring System API"}

# Diagnostic: Log all routes on startup
@app.on_event("startup")
async def startup_event():
    logger.info("--- REGISTERED ROUTES ---")
    for route in app.routes:
        if hasattr(route, "path"):
            logger.info(f"Registered Route: {route.path}")
    logger.info("--------------------------")
    websocket.start_webrtc_listener()

@app.on_event("shutdown")
async def shutdown_event():
    websocket.stop_webrtc_listener()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
