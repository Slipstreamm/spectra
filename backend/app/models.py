# This file will contain Pydantic models for API request/response validation
# and potentially ORM models if SQLAlchemy were to be used more extensively.

from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int

    model_config = {"from_attributes": True} # Pydantic V2 style

class ImageBase(BaseModel):
    filename: str
    # filepath will be server-side, not usually part of API model directly for creation
    mimetype: Optional[str] = None
    filesize: Optional[int] = None

class ImageCreate(ImageBase):
    tags: Optional[List[str]] = [] # Tags provided as strings during creation

class Image(ImageBase):
    id: int
    filepath: str # Or an HttpUrl to access the image
    uploaded_at: datetime
    tags: List[Tag] = []
    image_url: Optional[HttpUrl] = None # Field to be populated by a property or resolver

    model_config = {"from_attributes": True} # Pydantic V2 style

class ImageInDB(Image):
    # Potentially more fields that are in DB but not always returned to client
    pass

class PaginatedImages(BaseModel):
    limit: int
    offset: int
    total: int
    data: List[Image]
