import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
import magic # For python-magic

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
    # For now, let's construct it relative to the API structure.
    return f"{str(request.base_url).rstrip('/')}{settings.API_V1_STR}/static/uploads/{filename}"


@router.post("/upload/", response_model=models.Image, status_code=201)
@limiter.limit(settings.UPLOAD_RATE_LIMIT) # Apply specific rate limit for uploads using the imported limiter
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
        created_image_record.image_url = HttpUrl(get_image_url(request, created_image_record.filename))
        return created_image_record

    except Exception as e:
        # Clean up the saved file if DB operations fail
        if file_location_on_disk.exists():
            os.remove(file_location_on_disk)
        # Log the exception e
        print(f"Error during image upload DB processing: {e}")
        raise HTTPException(status_code=500, detail=f"Database error during image upload: {e}")


@router.get("/images/", response_model=models.PaginatedImages)
async def list_images(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by (e.g., 'cat,dog')"),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection) # Added redis dependency
):
    """
    Retrieve a paginated list of images.
    Supports filtering by tags (all provided tags must be present on an image).
    """
    tags_list = tags.split(',') if tags else None
    
    images_data = await crud.get_images(db=db, redis=redis, skip=skip, limit=limit, tags_filter=tags_list)
    total_count = await crud.count_images(db=db, redis=redis, tags_filter=tags_list)
    
    response_images = []
    for img_model in images_data: # crud.get_images now returns list of models.Image
        img_model.image_url = HttpUrl(get_image_url(request, img_model.filename))
        response_images.append(img_model)

    return models.PaginatedImages(limit=limit, offset=skip, total=total_count, data=response_images)


@router.get("/images/{image_id}/", response_model=models.Image)
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
    
    image_model.image_url = HttpUrl(get_image_url(request, image_model.filename))
    return image_model
