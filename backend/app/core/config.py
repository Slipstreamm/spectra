from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, AnyHttpUrl
from typing import List, Optional

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Image Board API"

    # PostgreSQL settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password" # Default, should be in .env
    POSTGRES_DB: str = "imageboard_db" # Default, should be in .env
    DATABASE_URL: Optional[PostgresDsn] = None

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None # Default, should be in .env
    REDIS_DB: int = 0
    REDIS_URL: Optional[RedisDsn] = None

    # Uploads directory
    UPLOADS_DIR: str = "backend/uploads" # Relative to project root
    MAX_FILE_SIZE_MB: int = 10 # Max file size in MB
    ALLOWED_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif", "image/webp"]

    # For constructing image URLs
    SERVER_HOST: AnyHttpUrl = "http://localhost:8000" # Base URL of the server

    # Rate limiting
    DEFAULT_RATE_LIMIT: str = "100/minute" # Default rate limit for general API access
    UPLOAD_RATE_LIMIT: str = "1/minute" # Specific rate limit for uploads

    # Security settings for JWT
    # IMPORTANT: SECRET_KEY should be a strong, random string and kept secret in production.
    # It's recommended to load this from an environment variable and not hardcode it.
    # For development, a default is provided. Generate a new one for production:
    # openssl rand -hex 32
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # 30 minutes

    # Pydantic V2 way to load from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    def __init__(self, **values):
        super().__init__(**values)
        if not self.DATABASE_URL:
            self.DATABASE_URL = PostgresDsn.build(
                scheme="postgresql", # Corrected scheme for asyncpg
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                path=self.POSTGRES_DB,
            )
        if not self.REDIS_URL:
            redis_path = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = RedisDsn.build(
                scheme="redis",
                host=self.REDIS_HOST,
                port=self.REDIS_PORT, # Pass as integer
                path=f"{redis_path}/{self.REDIS_DB}"
            )


settings = Settings()

# Example usage:
# from .config import settings
# print(settings.DATABASE_URL)
# print(settings.REDIS_URL)
