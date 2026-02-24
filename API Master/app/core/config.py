from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Windows Monitoring System API"
    API_V1_STR: str = "/api/v1"
    
    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "1234")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "montior_db")
    DATABASE_URL: Optional[str] = None

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "150.241.245.84")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Security
    SECRET_KEY: str = "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION" 
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 52560000  # 100 years
    REFRESH_TOKEN_EXPIRE_DAYS: int = 36500  # 100 years

    def resolve_database_url(self):
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"

settings = Settings()
settings.DATABASE_URL = settings.resolve_database_url()
