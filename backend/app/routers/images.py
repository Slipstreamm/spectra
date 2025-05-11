import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
import magic # For python-magic
import math # Added for ceil

import asyncpg
import redis.asyncio as redis_async # For type hinting
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     UploadFile, Request)
from pydantic import HttpUrl

from .. import crud, models # Removed schemas, using models for Pydantic models
from ..core.config import settings
from ..db import get_db_connection, get_redis_connection # Added get_redis_connection
from ..main import limiter # Import the limiter instance from main.py

router = APIRouter()

def get_image_url(request: Request, filename: str) -> str:
    # settings.API_V1_STR might be like "/api/v1"
    # The static mount is at f"{settings.API_V1_STR}/static/uploads"
    # So the URL should be request.url_for('static_uploads', path=filename)
    # However, request.url_for needs the name of the route, which is 'static_uploads'
    # and the path parameter for StaticFiles is 'path'.
    # Ensure settings.SERVER_HOST is correctly configured if absolute URLs are needed externally.
    
    base_url_str = str(request.base_url).rstrip('/') # Example: "http://localhost:8000"
    
    # Path components, ensure they are stripped of leading/trailing slashes
    # to be joined correctly.
    # settings.API_V1_STR is typically like "/api/v1"
    api_v1_segment = settings.API_V1_STR.strip('/') 
    static_segment = "static/uploads" # Static mount point relative to API_V1_STR
    filename_segment = filename.strip('/')
    
    # Filter out empty segments that might result from stripping if a segment was just "/" or empty
    path_parts = [s for s in [api_v1_segment, static_segment, filename_segment] if s]
    
    full_path = "/".join(path_parts) # Example: "api/v1/static/uploads/image.jpg"
    
    # Construct the full URL
    final_url = f"{base_url_str}/{full_path}"
    return final_url


@router.post("/upload/", response_model=models.Image, status_code=201)
@limiter.limit(settings.security.upload_rate_limit) # Apply specific rate limit for uploads using the imported limiter
async def upload_image(
    request: Request, # Add request for rate limiter
    file: UploadFile = File(...),
    tags_str: Optional[str] = Form(None), # Comma-separated tags as a string
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection) # Added redis dependency
):
    """
    Upload an image with optional tags.
    Tags are provided as a comma-separated string.
    """
    # Validate length of raw tags_str before splitting
    if tags_str and len(tags_str) > 1000: # Max 10 tags * 50 chars + 9 commas + some buffer ~ 600. 1000 is generous.
        raise HTTPException(status_code=413, detail="Tags string too long. Maximum 1000 characters allowed.")

    # Initial check based on client-provided Content-Type
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid image type (based on header). Allowed types: {settings.ALLOWED_MIME_TYPES}")

    # Robust check using python-magic by reading the start of the file
    # Read a chunk of the file to determine its type
    # SpooledTemporaryFile needs to be read carefully
    try:
        file_content_chunk = await file.read(2048) # Read first 2KB, should be enough for magic bytes
        await file.seek(0) # Reset file pointer to the beginning for subsequent operations (like saving)
        
        true_mime_type = magic.from_buffer(file_content_chunk, mime=True)
        
        if true_mime_type not in settings.ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid image type (based on content analysis: {true_mime_type}). Allowed types: {settings.ALLOWED_MIME_TYPES}")
        
        # If the client-provided type and server-verified type differ but both are allowed,
        # prefer the server-verified one for storage/metadata.
        # For now, we'll use the client's if it passed the initial check and content check passed.
        # Or, we can update file.content_type if we want to use the server-verified one.
        # Let's consider using the true_mime_type for the database record.
        # For now, the initial check is primary, this is a secondary stronger check.

    except Exception as e:
        # Log this error, could be an issue with reading the file or python-magic itself
        print(f"Error during magic number check: {e}")
        raise HTTPException(status_code=500, detail="Could not verify file content.")


    # Check file size (more robust check on actual content length if possible)
    # file.file is a SpooledTemporaryFile. We can get its size.
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0) # Reset file pointer
    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB")

    # Ensure uploads directory exists (it should be created on startup by main.py)
    # Construct absolute path for uploads_dir
    # __file__ is .../backend/app/routers/images.py
    # .parent -> .../backend/app/routers
    # .parent.parent -> .../backend/app
    # .parent.parent.parent -> .../backend
    # .parent.parent.parent.parent -> .../ (project root)
    project_root = Path(__file__).resolve().parent.parent.parent.parent 
    uploads_abs_path = project_root / settings.UPLOADS_DIR
    if not uploads_abs_path.exists():
        # This should ideally not happen if startup event in main.py works
        uploads_abs_path.mkdir(parents=True, exist_ok=True)
        print(f"Uploads directory was missing, created at: {uploads_abs_path}")


    # Generate a unique filename to prevent overwrites and for security
    original_filename = file.filename or "unknown_file"
    file_extension = Path(original_filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location_on_disk = uploads_abs_path / unique_filename
    
    # Save the file
    try:
        with open(file_location_on_disk, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
    except Exception as e:
        # Clean up if partial file was written?
        if file_location_on_disk.exists():
            os.remove(file_location_on_disk)
        raise HTTPException(status_code=500, detail=f"Could not save image file: {e}")
    finally:
        file.file.close()

    # Prepare data for database
    # Use the server-verified mime_type if available and different, otherwise client's
    # For simplicity, we'll stick to the client's file.content_type if it passed both checks.
    # A more robust approach might be to use `true_mime_type` from the magic check.
    # Let's update to use true_mime_type for the database.
    image_data = models.ImageCreate(
        filename=unique_filename, # Store the unique filename
        mimetype=true_mime_type, # Use server-verified MIME type
        filesize=file_size,
        tags=tags_str.split(',') if tags_str else []
    )
    
    # Relative path for DB storage (relative to UPLOADS_DIR base)
    # The filepath in DB should be just the unique_filename, as the base path is known.
    # Or, store it relative to the project root: settings.UPLOADS_DIR / unique_filename
    db_filepath = f"{settings.UPLOADS_DIR}/{unique_filename}"

    try:
        created_image_record = await crud.create_image_with_tags(
            db=db,
            redis=redis, # Pass redis client
            image_data=image_data,
            filepath_on_disk=db_filepath # Pass the path to be stored in DB
        )
        if not created_image_record:
            # This case implies DB operation failed in a way not raising an exception
            # Clean up the saved file
            if file_location_on_disk.exists():
                os.remove(file_location_on_disk)
            raise HTTPException(status_code=500, detail="Could not create image record in database.")

        # Populate the image_url for the response
        # The created_image_record is a dict or Row from DB. Convert to Pydantic model.
        # Assuming crud.create_image_with_tags returns a model.Image compatible structure
        
        # If crud returns a dict:
        # response_image = models.Image(**created_image_record, image_url=get_image_url(request, created_image_record['filename']))
        
        # If crud returns a models.Image instance (ideal):
        # Pydantic V2 will validate the string against HttpUrl type annotation
        created_image_record.image_url = get_image_url(request, created_image_record.filename)
        return created_image_record

    except Exception as e:
        # Clean up the saved file if DB operations fail
        if file_location_on_disk.exists():
            os.remove(file_location_on_disk)
        # Log the exception e
        print(f"Error during image upload DB processing: {e}")
        raise HTTPException(status_code=500, detail=f"Database error during image upload: {e}")


@router.get("/images/", response_model=models.PaginatedPosts)
async def list_images(
    request: Request,
    page: int = Query(1, ge=1, description="Page number for pagination (1-indexed)"),
    limit: int = Query(settings.DEFAULT_IMAGES_PER_PAGE, ge=1, le=settings.MAX_IMAGES_PER_PAGE, description="Number of images per page"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by (e.g., 'nature,sky')"),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    """
    Retrieve a paginated list of images, supporting tag-based filtering.
    The frontend expects `page` (1-indexed) and `limit`.
    The response should include `total_items`, `total_pages`, and `current_page`.
    """
    tags_list = tags.split(',') if tags and tags.strip() else None

    # Calculate skip/offset for CRUD operations
    skip = (page - 1) * limit

    images_from_db = await crud.get_images(db=db, redis=redis, skip=skip, limit=limit, tags_filter=tags_list)
    total_items = await crud.count_images(db=db, redis=redis, tags_filter=tags_list)

    if total_items == 0:
        total_pages = 0
    else:
        total_pages = math.ceil(total_items / limit)
    
    # If requested page is out of bounds after filtering, return empty list for current page
    # but still provide correct total_items and total_pages.
    # Example: 10 items, limit 5. total_pages = 2. If page=3 requested, data is empty.
    if page > total_pages and total_items > 0 : # if total_items is 0, page will be 1, total_pages 0. page > total_pages.
        # This ensures that if a page beyond the actual number of pages is requested,
        # we return an empty list for `data` but correct pagination metadata.
        # However, crud.get_images would likely return an empty list anyway if skip is too high.
        # This check is more for clarity or if crud.get_images had different behavior.
        # For now, we'll rely on crud.get_images to return empty if skip is out of bounds.
        pass


    frontend_images: List[models.ImageForFrontend] = []
    for img_model in images_from_db: # img_model is models.Image
        # Ensure image_url is populated
        img_model.image_url = get_image_url(request, img_model.filename)
        
        # For now, thumbnail_url will be the same as image_url.
        # In a real scenario, this might point to a specifically generated thumbnail.
        img_model.thumbnail_url = img_model.image_url

        # Transform tags from List[models.Tag] to List[models.FrontendTag]
        frontend_tags = [models.FrontendTag(name=tag.name) for tag in img_model.tags]

        frontend_images.append(
            models.ImageForFrontend(
                id=img_model.id,
                filename=img_model.filename,
                uploaded_at=img_model.uploaded_at,
                tags=frontend_tags,
                image_url=img_model.image_url, # Already HttpUrl
                thumbnail_url=img_model.thumbnail_url # Also HttpUrl
            )
        )

    return models.PaginatedPosts(
        data=frontend_images,
        total_items=total_items,
        total_pages=total_pages,
        current_page=page
    )


@router.get("/images/{image_id}/", response_model=models.Image) # Keeping original response model for single image
async def get_image_details(
    request: Request,
    image_id: int,
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection) # Added redis dependency
):
    """
    Retrieve details for a single image by its ID.
    """
    image_model = await crud.get_image(db=db, redis=redis, image_id=image_id) # crud.get_image returns models.Image or None
    if image_model is None:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image_model.image_url = get_image_url(request, image_model.filename) # Pydantic V2 validation
    return image_model
