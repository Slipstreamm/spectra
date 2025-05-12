from fastapi import APIRouter
from pydantic import BaseModel
from ..core.config import settings, ThemeSettings, SiteSettings # Import SiteSettings

router = APIRouter()

# Pydantic model for the site info response
class SiteInfoResponse(BaseModel):
    name: str
    description: str

@router.get("/theme-config", response_model=ThemeSettings, tags=["Utils"])
async def get_theme_config():
    """
    Provides the theme configuration (light and dark mode colors)
    as defined in the server's configuration.
    """
    return settings.theme

@router.get("/site-info", response_model=SiteInfoResponse, tags=["Utils"])
async def get_site_info():
    """
    Provides the site's name and description as defined in the server's configuration.
    """
    return SiteInfoResponse(name=settings.site.name, description=settings.site.description)
