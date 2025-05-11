# This file will contain Pydantic models for API request/response validation
# and potentially ORM models if SQLAlchemy were to be used more extensively.

from pydantic import BaseModel, HttpUrl, constr, Field, field_validator, model_validator
from typing import List, Optional, ForwardRef, Dict, Any
from datetime import datetime

# ForwardRef for self-referencing Pydantic models (e.g., Comment replies)
Comment = ForwardRef('Comment')

class TagBase(BaseModel):
    name: constr(strip_whitespace=True, to_lower=True, min_length=1, max_length=50)

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int

    model_config = {"from_attributes": True}

# User models (essential for posts, comments, votes)
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

# Post models (renamed from Image)
class PostBase(BaseModel):
    filename: str # filename of the image associated with the post
    mimetype: Optional[str] = None
    filesize: Optional[int] = None
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)
    # uploader_id will be set by the backend based on authenticated user

class PostCreate(PostBase):
    tags: Optional[List[constr(strip_whitespace=True, to_lower=True, min_length=1, max_length=50)]] = Field(default_factory=list, max_items=20) # Increased max_items for tags

class Post(PostBase):
    id: int
    filepath: str # Path on disk, or relative path
    uploaded_at: datetime
    uploader_id: Optional[int] = None
    uploader: Optional[User] = None # To embed uploader info
    tags: List[Tag] = []
    image_url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None
    comment_count: int = 0
    upvotes: int = 0
    downvotes: int = 0
    # comments: List[Comment] = [] # Potentially include top-level comments here

    model_config = {"from_attributes": True}

class PostInDB(Post):
    pass # May include fields not always sent to client

# Model for individual tag as expected by frontend (name only)
class FrontendTag(BaseModel):
    name: str

# Model for individual post as expected by frontend
class PostForFrontend(BaseModel):
    id: int
    filename: str
    title: Optional[str] = None
    description: Optional[str] = None
    uploaded_at: datetime
    uploader: Optional[UserBase] = None # Display basic user info
    tags: List[FrontendTag] = []
    image_url: HttpUrl
    thumbnail_url: Optional[HttpUrl] = None
    comment_count: int = 0
    upvotes: int = 0
    downvotes: int = 0

    model_config = {"from_attributes": True}

class PaginatedPosts(BaseModel):
    data: List[PostForFrontend]
    total_items: int
    total_pages: int
    current_page: int

# Comment models
class CommentBase(BaseModel):
    content: constr(strip_whitespace=True, min_length=1, max_length=5000)

class CommentCreate(CommentBase):
    # post_id is part of the path in API, user_id from auth
    parent_comment_id: Optional[int] = None

class CommentUpdate(BaseModel):
    content: Optional[constr(strip_whitespace=True, min_length=1, max_length=5000)] = None

class Comment(CommentBase):
    id: int
    post_id: int
    user_id: int
    user: Optional[UserBase] = None # Embed basic user info
    parent_comment_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    replies: List['Comment'] = [] # For nested comments
    upvotes: int = 0
    downvotes: int = 0
    # depth: Optional[int] = 0 # Could be useful for frontend rendering

    model_config = {"from_attributes": True}

# Update forward reference
Comment.model_rebuild()


# Vote models
class VoteBase(BaseModel):
    vote_type: int = Field(..., ge=-1, le=1) # -1 for downvote, 1 for upvote

    @field_validator('vote_type')
    def vote_type_must_be_valid(cls, v: int) -> int:
        if v not in [-1, 1]:
            raise ValueError('vote_type must be -1 or 1')
        return v

class VoteCreate(VoteBase):
    # One of these must be provided, handled by API logic
    post_id: Optional[int] = None
    comment_id: Optional[int] = None

    @model_validator(mode='before')
    @classmethod
    def check_target_exclusivity(cls, data: Any) -> Any:
        if isinstance(data, dict):
            post_id_present = data.get('post_id') is not None
            comment_id_present = data.get('comment_id') is not None

            if post_id_present == comment_id_present: # True if both are present or both are absent
                raise ValueError('Either post_id or comment_id must be provided, but not both.')
        return data


class Vote(VoteBase):
    id: int
    user_id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    created_at: datetime
    user: Optional[UserBase] = None # Embed basic user info for context if needed

    model_config = {"from_attributes": True}

# For displaying vote counts on posts/comments
class VoteCounts(BaseModel):
    upvotes: int
    downvotes: int
