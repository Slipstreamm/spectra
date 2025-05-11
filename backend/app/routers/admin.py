from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Annotated, List
import asyncpg
import redis.asyncio as redis_async
import os # For file deletion

from .. import models, crud
from ..core.config import settings
from ..db import get_db_connection, get_redis_connection
from .auth import get_current_active_superuser # Import the dependency

router = APIRouter()

# Admin specific CRUD operations might be added here or in crud.py

@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def delete_image_admin(
    image_id: int,
    request: Request, # To access app.state for project_root if needed for path construction
    current_user: Annotated[models.User, Depends(get_current_active_superuser)],
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    """
    Delete an image by its ID. Only accessible by superusers.
    This will delete the image record from the database and the file from disk.
    """
    image_to_delete = await crud.get_image(db=db, redis=redis, image_id=image_id) # get_image already handles cache
    
    if not image_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Construct the full path to the image file for deletion
    # Assuming image_to_delete.filepath is relative to project root like "backend/uploads/filename.jpg"
    # or an absolute path. If relative, need to join with project root.
    # settings.UPLOADS_DIR is "backend/uploads"
    # image_to_delete.filepath should be like "backend/uploads/actual_file_name.jpg"
    
    # Determine project root. Assuming main.py is in backend/app/
    # This logic might be better placed in a utility or config if used widely.
    # For now, let's reconstruct it similarly to main.py's startup.
    # A more robust way would be to pass project_root via app.state if consistently needed.
    # Let's assume filepath is stored as an absolute path or a path that os.remove can handle.
    # If filepath is stored as "backend/uploads/image.jpg", we need to prepend project root.
    
    # Simplification: Assume filepath is directly usable by os.remove or is absolute.
    # If it's relative to project root, this needs adjustment.
    # Let's assume image_to_delete.filepath is the full absolute path or resolvable from CWD.
    # Given the setup in main.py, filepath is likely stored as something like:
    # "z:/projects_git/spectra/backend/uploads/image.jpg" if settings.UPLOADS_DIR was used with abspath
    # Or just "backend/uploads/image.jpg" if stored relative to project root.
    
    # Let's assume filepath is stored relative to the project root.
    # We need to construct the absolute path.
    # This is a common source of issues if not handled carefully.
    # The `main.py` constructs `uploads_abs_path` for serving. We need similar logic for deletion.
    # `os.path.dirname(__file__)` in this router file is `z:/projects_git/spectra/backend/app/routers`
    project_root_from_router = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    
    # If image_to_delete.filepath is like "backend/uploads/image.jpg"
    file_to_delete_path = os.path.join(project_root_from_router, image_to_delete.filepath)

    try:
        # 1. Delete from database (CASCADE should handle image_tags)
        # We need a specific DB delete function. Let's add one to crud.py
        # For now, let's assume a direct execute. This is not ideal.
        # A proper crud.delete_image function should be created.
        
        # Placeholder for actual DB deletion logic:
        # await crud.delete_image_db(db=db, image_id=image_id)
        # For now, let's write a direct query (less ideal than a CRUD function)
        async with db.transaction():
            # First, delete from image_tags (though CASCADE should handle this)
            await db.execute("DELETE FROM image_tags WHERE image_id = $1", image_id)
            # Then, delete from images
            result = await db.execute("DELETE FROM images WHERE id = $1", image_id)
            if result == "DELETE 0": # Check if any row was actually deleted
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found in DB for deletion.")


        # 2. Delete file from disk
        if os.path.exists(file_to_delete_path):
            os.remove(file_to_delete_path)
        else:
            # Log a warning if file not found, but proceed if DB entry was deleted
            print(f"Warning: File not found for deletion: {file_to_delete_path}")

        # 3. Invalidate cache for the deleted image and any lists
        await redis.delete(f"{crud.IMAGE_CACHE_PREFIX}{image_id}")
        
        # Broad cache invalidation for lists and counts (similar to create_image_with_tags)
        list_cache_keys = [key async for key in redis.scan_iter(match=f"{crud.IMAGE_LIST_CACHE_PREFIX}*")]
        if list_cache_keys:
            await redis.delete(*list_cache_keys)
        
        count_cache_keys = [key async for key in redis.scan_iter(match=f"{crud.IMAGE_COUNT_CACHE_PREFIX}*")]
        if count_cache_keys:
            await redis.delete(*count_cache_keys)
            
    except Exception as e:
        # Log the exception
        print(f"Error deleting image {image_id}: {e}")
        # Re-raise as HTTPException to inform client
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting image: {str(e)}")

    return # Returns 204 No Content on success

# Endpoint to list all images (paginated) - for admin use
@router.get("/images", response_model=models.PaginatedPosts, tags=["Admin"]) # Changed to PaginatedPosts
async def list_all_images_admin(
    request: Request, # Added request parameter
    current_user: Annotated[models.User, Depends(get_current_active_superuser)],
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
    skip: int = 0,
    limit: int = 20 # Admin might want more per page
):
    """
    Retrieve all images with pagination. Accessible by superusers.
    """
    # This reuses the existing crud.get_images and crud.count_images
    # Ensure these functions correctly build image_url if needed, or handle it here.
    # For admin, raw filepaths might be fine, or full URLs.
    
    images_list = await crud.get_images(db=db, redis=redis, skip=skip, limit=limit, tags_filter=None)
    total_images = await crud.count_images(db=db, redis=redis, tags_filter=None)

    # Populate image_url for each image (similar to images.py router)
    for img in images_list:
        if img.filename: # filename should be directly usable
            # Construct URL based on how static files are served
            # Use request.base_url for scheme and host, then construct path carefully
            base_url_str = str(request.base_url).rstrip('/')
            api_v1_segment = settings.API_V1_STR.strip('/')
            static_segment = "static/uploads"
            filename_segment = img.filename.strip('/')
            
            path_parts = [s for s in [api_v1_segment, static_segment, filename_segment] if s]
            full_path = "/".join(path_parts)
            
            img.image_url = f"{base_url_str}/{full_path}" # Pydantic V2 validation
            # Ensure thumbnail_url is also populated if PostForFrontend expects it
            if hasattr(img, 'thumbnail_url'):
                img.thumbnail_url = img.image_url # Placeholder for now
            
    # The PaginatedPosts model expects current_page, total_pages, total_items, data
    # Need to adapt the return to match models.PaginatedPosts structure
    total_pages_val = (total_images + limit - 1) // limit if limit > 0 else 0
    current_page_val = (skip // limit) + 1 if limit > 0 else 1
    
    # Data needs to be List[PostForFrontend]
    # The crud.get_images currently returns List[models.Image] (which should be models.Post)
    # We need to ensure the data being passed is compatible or transformed.
    # For now, assuming images_list contains items compatible with PostForFrontend after URL population.
    # This part might need further adjustment based on actual return type of crud.get_posts
    # and the structure of PostForFrontend.

    # Assuming images_list contains models.Post instances, convert to PostForFrontend
    frontend_data = []
    for post_model in images_list: # Assuming images_list are models.Post
        uploader_base = None
        if post_model.uploader:
            uploader_base = models.UserBase(email=post_model.uploader.email, username=post_model.uploader.username)

        frontend_tags_list = [models.FrontendTag(name=tag.name) for tag in post_model.tags]

        frontend_data.append(models.PostForFrontend(
            id=post_model.id,
            filename=post_model.filename,
            title=getattr(post_model, 'title', None), # getattr for safety if field is missing
            description=getattr(post_model, 'description', None),
            uploaded_at=post_model.uploaded_at,
            uploader=uploader_base,
            tags=frontend_tags_list,
            image_url=post_model.image_url,
            thumbnail_url=getattr(post_model, 'thumbnail_url', post_model.image_url), # Use image_url as fallback
            comment_count=getattr(post_model, 'comment_count', 0),
            upvotes=getattr(post_model, 'upvotes', 0),
            downvotes=getattr(post_model, 'downvotes', 0)
        ))

    return models.PaginatedPosts(
        data=frontend_data,
        total_items=total_images,
        total_pages=total_pages_val,
        current_page=current_page_val
    )
