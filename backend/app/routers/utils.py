from fastapi import APIRouter
from ..core.config import settings, ThemeSettings # Import ThemeSettings for response model

router = APIRouter()

@router.get("/theme-config", response_model=ThemeSettings, tags=["Utils"])
async def get_theme_config():
    """
    Provides the theme configuration (light and dark mode colors)
    as defined in the server's configuration.
    """
    return settings.theme
