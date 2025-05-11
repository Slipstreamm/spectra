from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Annotated, List
import asyncpg
import redis.asyncio as redis_async
import os # For file deletion

from .. import models, crud
from ..core.config import settings
from ..db import get_db_connection, get_redis_connection
# from .auth import get_current_active_superuser # This is removed
from .auth import require_admin_owner # Import new role-based dependency

router = APIRouter()

# Admin specific CRUD operations might be added here or in crud.py

@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"])
async def delete_image_admin( # Renamed to delete_post_admin
    post_id: int, # Changed from image_id to post_id
    request: Request,
    current_user: Annotated[models.User, Depends(require_admin_owner)], # Use new dependency
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    """
    Delete a post by its ID. Only accessible by admin/owner.
    This will delete the post record from the database and the associated file from disk.
    """
    post_to_delete = await crud.get_post(db=db, redis=redis, post_id=post_id)
    
    if not post_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Construct the full path to the image file for deletion
    # post_to_delete.filepath should be like "backend/uploads/actual_file_name.jpg"
    
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
    
    # If post_to_delete.filepath is like "backend/uploads/image.jpg"
    file_to_delete_path = os.path.join(project_root_from_router, post_to_delete.filepath)

    try:
        # 1. Delete from database (CASCADE should handle post_tags, comments, votes)
        # A proper crud.delete_post function should be created.
        async with db.transaction():
            # CASCADE constraints on foreign keys in post_tags, comments, votes referencing posts.id
            # should handle deletion of related records.
            result = await db.execute("DELETE FROM posts WHERE id = $1", post_id)
            if result == "DELETE 0": # Check if any row was actually deleted
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found in DB for deletion.")

        # 2. Delete file from disk
        if os.path.exists(file_to_delete_path):
            os.remove(file_to_delete_path)
        else:
            print(f"Warning: File not found for deletion: {file_to_delete_path}")

        # 3. Invalidate cache for the deleted post and any lists
        await redis.delete(f"{crud.POST_CACHE_PREFIX}{post_id}") # Use POST_CACHE_PREFIX
        
        list_cache_keys = [key async for key in redis.scan_iter(match=f"{crud.POST_LIST_CACHE_PREFIX}*")]
        if list_cache_keys:
            await redis.delete(*list_cache_keys)
        
        count_cache_keys = [key async for key in redis.scan_iter(match=f"{crud.POST_COUNT_CACHE_PREFIX}*")]
        if count_cache_keys:
            await redis.delete(*count_cache_keys)
            
    except Exception as e:
        print(f"Error deleting post {post_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting post: {str(e)}")

    return # Returns 204 No Content on success

# Endpoint to list all posts (paginated) - for admin use
@router.get("/posts", response_model=models.PaginatedPosts, tags=["Admin"]) # Changed path from /images to /posts
async def list_all_posts_admin(
    request: Request,
    current_user: Annotated[models.User, Depends(require_admin_owner)], # Use new dependency
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
    skip: int = 0,
    limit: int = 20
):
    """
    Retrieve all posts with pagination. Accessible by admin/owner.
    """
    posts_list = await crud.get_posts(db=db, redis=redis, skip=skip, limit=limit, tags_filter=None) # Use crud.get_posts
    total_posts = await crud.count_posts(db=db, redis=redis, tags_filter=None) # Use crud.count_posts

    for post_model in posts_list: # post_model is models.Post
        if post_model.filename:
            base_url_str = str(request.base_url).rstrip('/')
            api_v1_segment = settings.API_V1_STR.strip('/')
            static_segment = "static/uploads"
            filename_segment = post_model.filename.strip('/')
            path_parts = [s for s in [api_v1_segment, static_segment, filename_segment] if s]
            full_path = "/".join(path_parts)
            post_model.image_url = f"{base_url_str}/{full_path}"
            if hasattr(post_model, 'thumbnail_url'): # Ensure thumbnail_url is also populated
                post_model.thumbnail_url = post_model.image_url # Placeholder

    total_pages_val = (total_posts + limit - 1) // limit if limit > 0 else 0
    current_page_val = (skip // limit) + 1 if limit > 0 else 1
    
    frontend_data = []
    for post_model in posts_list:
        uploader_base = None
        if post_model.uploader:
            # Ensure role is included when creating UserBase for PostForFrontend
            uploader_base = models.UserBase(
                email=post_model.uploader.email, 
                username=post_model.uploader.username,
                role=post_model.uploader.role 
            )
        frontend_tags_list = [models.FrontendTag(name=tag.name) for tag in post_model.tags]
        frontend_data.append(models.PostForFrontend(
            id=post_model.id,
            filename=post_model.filename,
            title=post_model.title,
            description=post_model.description,
            uploaded_at=post_model.uploaded_at,
            uploader=uploader_base,
            tags=frontend_tags_list,
            image_url=post_model.image_url,
            thumbnail_url=getattr(post_model, 'thumbnail_url', post_model.image_url),
            comment_count=post_model.comment_count,
            upvotes=post_model.upvotes,
            downvotes=post_model.downvotes
        ))

    return models.PaginatedPosts(
        data=frontend_data,
        total_items=total_posts,
        total_pages=total_pages_val,
        current_page=current_page_val
    )
