import tomllib # Using tomllib for Python 3.11+ TOML parsing
from pydantic import BaseModel as PydanticBaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional, List, Any, Dict
from urllib.parse import quote_plus

# Define the path to the config.toml file, assuming it's in the 'backend' directory
# __file__ is .../backend/app/core/config.py
# .parent -> .../backend/app/core
# .parent.parent -> .../backend/app
# .parent.parent.parent -> .../backend
CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "config.toml"
print(f"Loading configuration from {CONFIG_FILE_PATH}")

# --- Nested Pydantic Models for TOML Structure ---
class SiteSettings(PydanticBaseModel):
    name: str = "Spectra Gallery"
    description: str = "An open-source image board."

class ThemeColors(PydanticBaseModel):
    bg_color: str = "#000000" # Default fallback
    text_color: str = "#ffffff"
    primary_color: str = "#007bff"
    secondary_color: str = "#6c757d"
    card_bg_color: str = "#333333"
    border_color: str = "#444444"
    header_bg_color: str = "#222222"
    button_bg_color: str = "#555555"
    button_text_color: str = "#ffffff"
    button_hover_bg_color: str = "#777777"
    input_bg_color: str = "#444444"
    input_border_color: str = "#666666"
    modal_bg_color: str = "rgba(0,0,0,0.7)"
    modal_content_bg_color: str = "#3a3a3a"

class ThemeSettings(PydanticBaseModel):
    dark: ThemeColors = ThemeColors() # Provide default instances
    light: ThemeColors = ThemeColors(
        bg_color="#ffffff", text_color="#000000", primary_color="#0056b3", 
        card_bg_color="#f8f9fa", border_color="#dee2e6" 
        # Add other light theme defaults if different from dark's structure
    )

class DatabaseSettings(PydanticBaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "password"
    name: str = "imageboard_db"

class RedisSettings(PydanticBaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

class SecuritySettings(PydanticBaseModel):
    secret_key: str = "fallback-secret-key-if-not-in-toml-or-env"
    access_token_expire_minutes: int = 30
    upload_rate_limit: str = "10/minute"
    default_rate_limit: str = "200/minute"

# --- Main Settings Class ---
class Settings(BaseSettings):
    # Top-level settings that might not be in TOML or have defaults here
    # These can still be overridden by environment variables (e.g., API_V1_STR=...)
    API_V1_STR: str = "/api/v1"
    SERVER_HOST: HttpUrl = Field(default_factory=lambda: HttpUrl("http://localhost:8000")) # Use HttpUrl for validation
    
    # Settings that will be primarily loaded from TOML or have their defaults here
    # if not specified in TOML. These are less likely to be ENV vars unless prefixed.
    UPLOADS_DIR: str = "frontend/static/uploads" 
    ALLOWED_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    MAX_FILE_SIZE_MB: int = 5
    DEFAULT_IMAGES_PER_PAGE: int = 20
    MAX_IMAGES_PER_PAGE: int = 100

    # Nested settings from TOML (or their defaults if TOML section is missing)
    site: SiteSettings = Field(default_factory=SiteSettings)
    theme: ThemeSettings = Field(default_factory=ThemeSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    
    DATABASE_URL: Optional[str] = None # Will be constructed
    REDIS_URL: Optional[str] = None # Will be constructed

    model_config = SettingsConfigDict(
        env_file=".env",  # Still support .env for overrides or non-TOML settings
        env_nested_delimiter='__', # e.g., DATABASE__HOST to override database.host
        extra='ignore' # Ignore extra fields from .env or TOML not defined in model
    )

    def __init__(self, **values: Any):
        # Load from TOML first
        toml_config = self._load_toml_config()
        
        # Pydantic-settings will load from .env and ENV variables automatically.
        # We need to ensure TOML values are passed to super().__init__()
        # and that ENV variables can override them.
        # The order of precedence: ENV > .env > TOML > model defaults.
        # Pydantic-settings handles ENV and .env. We inject TOML before that.
        
        # Merge TOML config with any explicitly passed values
        # Values passed to __init__ take precedence over TOML for this initial merge
        merged_init_and_toml = {**toml_config, **values}

        super().__init__(**merged_init_and_toml)

        # Construct DATABASE_URL after all settings are loaded
        if not self.DATABASE_URL: # If not set by ENV or .env or TOML (if DATABASE_URL was a direct TOML field)
            # asyncpg expects the scheme to be 'postgresql' or 'postgres', not 'postgresql+asyncpg'
            encoded_password = quote_plus(self.database.password)
            self.DATABASE_URL = f"postgresql://{self.database.user}:{encoded_password}@{self.database.host}:{self.database.port}/{self.database.name}"

        # Construct REDIS_URL
        if not self.REDIS_URL:
            self.REDIS_URL = f"redis://{self.redis.host}:{self.redis.port}/{self.redis.db}"

    @classmethod
    def _load_toml_config(cls) -> Dict[str, Any]:
        if not CONFIG_FILE_PATH.exists():
            print(f"Warning: Configuration file not found at {CONFIG_FILE_PATH}")
            return {}
        try:
            with open(CONFIG_FILE_PATH, "rb") as f: # tomllib expects bytes
                return tomllib.load(f)
        except Exception as e:
            print(f"Error loading TOML configuration from {CONFIG_FILE_PATH}: {e}")
            return {}

settings = Settings()

# Example of how to access:
# print(settings.site.name)
# print(settings.theme.dark.primary_color)
# print(settings.database.host)
# print(settings.API_V1_STR) # Can be overridden by ENV var API_V1_STR
# print(settings.database.port) # Can be overridden by ENV var DATABASE__PORT
