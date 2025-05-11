import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
import magic # For python-magic
import math

import asyncpg
import redis.asyncio as redis_async
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     UploadFile, Request)
from pydantic import HttpUrl

from .. import crud, models
from ..core.config import settings
from ..core import security # For get_current_active_user
from ..db import get_db_connection, get_redis_connection
from ..main import limiter

router = APIRouter(
    prefix="/posts",
    tags=["posts"],
)

def get_post_image_url(request: Request, filename: str) -> str:
    base_url_str = str(request.base_url).rstrip('/')
    api_v1_segment = settings.API_V1_STR.strip('/')
    static_segment = "static/uploads" # Assuming uploads are still served from here
    filename_segment = filename.strip('/')
    path_parts = [s for s in [api_v1_segment, static_segment, filename_segment] if s]
    full_path = "/".join(path_parts)
    return f"{base_url_str}/{full_path}"

@router.post("/", response_model=models.Post, status_code=201) # Changed from /upload/ to /
@limiter.limit(settings.security.upload_rate_limit)
async def upload_post(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags_str: Optional[str] = Form(None),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """
    Upload an image as part of a new post, with optional title, description, and tags.
    """
    if tags_str and len(tags_str) > 1000:
        raise HTTPException(status_code=413, detail="Tags string too long.")
    if title and len(title) > 255:
        raise HTTPException(status_code=413, detail="Title too long. Maximum 255 characters.")

    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid image type (header). Allowed: {settings.ALLOWED_MIME_TYPES}")

    try:
        file_content_chunk = await file.read(2048)
        await file.seek(0)
        true_mime_type = magic.from_buffer(file_content_chunk, mime=True)
        if true_mime_type not in settings.ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid image type (content: {true_mime_type}). Allowed: {settings.ALLOWED_MIME_TYPES}")
    except Exception as e:
        print(f"Error during magic number check: {e}")
        raise HTTPException(status_code=500, detail="Could not verify file content.")

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB")

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    uploads_abs_path = project_root / settings.UPLOADS_DIR
    if not uploads_abs_path.exists():
        uploads_abs_path.mkdir(parents=True, exist_ok=True)

    original_filename = file.filename or "unknown_file"
    file_extension = Path(original_filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location_on_disk = uploads_abs_path / unique_filename

    try:
        with open(file_location_on_disk, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
    except Exception as e:
        if file_location_on_disk.exists(): os.remove(file_location_on_disk)
        raise HTTPException(status_code=500, detail=f"Could not save image file: {e}")
    finally:
        file.file.close()

    post_data_create = models.PostCreate(
        filename=unique_filename,
        mimetype=true_mime_type,
        filesize=file_size,
        title=title,
        description=description,
        tags=tags_str.split(',') if tags_str else []
    )
    
    db_filepath = f"{settings.UPLOADS_DIR}/{unique_filename}"

    try:
        created_post_record = await crud.create_post_with_tags(
            db=db, redis=redis, post_data=post_data_create,
            filepath_on_disk=db_filepath, uploader_id=current_user.id
        )
        if not created_post_record:
            if file_location_on_disk.exists(): os.remove(file_location_on_disk)
            raise HTTPException(status_code=500, detail="Could not create post record in database.")

        created_post_record.image_url = get_post_image_url(request, created_post_record.filename)
        created_post_record.thumbnail_url = created_post_record.image_url # Placeholder
        return created_post_record
    except Exception as e:
        if file_location_on_disk.exists(): os.remove(file_location_on_disk)
        print(f"Error during post upload DB processing: {e}")
        raise HTTPException(status_code=500, detail=f"Database error during post upload: {str(e)}")


@router.get("/", response_model=models.PaginatedPosts)
async def list_posts(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(settings.DEFAULT_IMAGES_PER_PAGE, ge=1, le=settings.MAX_IMAGES_PER_PAGE),
    tags: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    tags_list = tags.split(',') if tags and tags.strip() else None
    skip = (page - 1) * limit

    posts_from_db = await crud.get_posts(db=db, redis=redis, skip=skip, limit=limit, tags_filter=tags_list)
    total_items = await crud.count_posts(db=db, redis=redis, tags_filter=tags_list)
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    
    frontend_posts: List[models.PostForFrontend] = []
    for post_model in posts_from_db: # post_model is models.Post
        image_url = get_post_image_url(request, post_model.filename)
        thumbnail_url = image_url # Placeholder

        # Transform tags from List[models.Tag] to List[models.FrontendTag]
        frontend_tags = [models.FrontendTag(name=tag.name) for tag in post_model.tags]
        
        uploader_frontend = None
        if post_model.uploader:
             uploader_frontend = models.UserBase(
                email=post_model.uploader.email,
                username=post_model.uploader.username
                # id, is_active, is_superuser, created_at are not in UserBase
            )

        frontend_posts.append(
            models.PostForFrontend(
                id=post_model.id,
                filename=post_model.filename,
                title=post_model.title,
                description=post_model.description,
                uploaded_at=post_model.uploaded_at,
                uploader=uploader_frontend,
                tags=frontend_tags,
                image_url=image_url,
                thumbnail_url=thumbnail_url,
                comment_count=post_model.comment_count,
                upvotes=post_model.upvotes,
                downvotes=post_model.downvotes
            )
        )

    return models.PaginatedPosts(
        data=frontend_posts,
        total_items=total_items,
        total_pages=total_pages,
        current_page=page
    )

@router.get("/{post_id}/", response_model=models.Post)
async def get_post_details(
    request: Request,
    post_id: int,
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    post_model = await crud.get_post(db=db, redis=redis, post_id=post_id)
    if post_model is None:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post_model.image_url = get_post_image_url(request, post_model.filename)
    post_model.thumbnail_url = post_model.image_url # Placeholder
    return post_model
