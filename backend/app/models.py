# This file will contain Pydantic models for API request/response validation
# and potentially ORM models if SQLAlchemy were to be used more extensively.

from pydantic import BaseModel, HttpUrl, constr, Field
from typing import List, Optional
from datetime import datetime

class TagBase(BaseModel):
    name: constr(strip_whitespace=True, to_lower=True, min_length=1, max_length=50)

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
    # Ensure individual tags also conform to constraints, and limit the number of tags.
    tags: Optional[List[constr(strip_whitespace=True, to_lower=True, min_length=1, max_length=50)]] = Field(default_factory=list, max_items=10)


class Image(ImageBase):
    id: int
    filepath: str # Or an HttpUrl to access the image
    uploaded_at: datetime
    tags: List[Tag] = []
    image_url: Optional[HttpUrl] = None # Field to be populated by a property or resolver
    thumbnail_url: Optional[HttpUrl] = None # Added for frontend compatibility

    model_config = {"from_attributes": True} # Pydantic V2 style

class ImageInDB(Image):
    # Potentially more fields that are in DB but not always returned to client
    pass

# Model for individual image tag as expected by frontend (name only)
class FrontendTag(BaseModel):
    name: str

# Model for individual image as expected by frontend
class ImageForFrontend(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime # FastAPI will convert to ISO string
    tags: List[FrontendTag] = []
    image_url: HttpUrl # Should always be present for frontend
    thumbnail_url: Optional[HttpUrl] = None

    model_config = {"from_attributes": True}


class PaginatedImages(BaseModel): # Renamed from PaginatedImagesResponse
    data: List[ImageForFrontend]
    total_items: int
    total_pages: int
    current_page: int

# User models
class UserBase(BaseModel):
    email: str = Field(..., example="admin@example.com")
    username: str = Field(..., min_length=3, max_length=50, example="admin_user")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, example="aSecurePassword123!")
    is_superuser: bool = False

class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class User(UserBase):
    id: int
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

class UserInDB(User):
    hashed_password: str
