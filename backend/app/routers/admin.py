from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Annotated, List, Optional
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

# For python-magic, ensure it's available
try:
    import magic
except ImportError:
    magic = None # Fallback if not installed, though it's in requirements.txt

import uuid
import shutil
from pathlib import Path
from fastapi import File, UploadFile, Form # For File and UploadFile

# Helper to construct image URLs, similar to posts.py
def get_admin_post_image_url(request: Request, filename: str) -> str:
    base_url_str = str(request.base_url).rstrip('/')
    api_v1_segment = settings.API_V1_STR.strip('/')
    static_segment = "static/uploads"
    filename_segment = filename.strip('/')
    path_parts = [s for s in [api_v1_segment, static_segment, filename_segment] if s]
    full_path = "/".join(path_parts)
    return f"{base_url_str}/{full_path}"


@router.post("/posts/batch-upload", status_code=status.HTTP_201_CREATED, tags=["Admin"])
async def batch_upload_posts_admin(
    request: Request,
    current_user: Annotated[models.User, Depends(require_admin_owner)],
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
    files: List[UploadFile] = File(...),
    tags_str: Optional[str] = Form(None) # Common tags for all files in this batch
):
    """
    Batch upload multiple images. Admins/Owners only.
    Applies a common set of tags to all uploaded images.
    Titles and descriptions can be auto-generated or left blank.
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided for batch upload.")

    if not magic:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File type verification (magic) is not available.")

    project_root = Path(__file__).resolve().parent.parent.parent.parent # z:/projects_git/spectra
    uploads_abs_path = project_root / settings.UPLOADS_DIR # z:/projects_git/spectra/backend/uploads
    if not uploads_abs_path.exists():
        uploads_abs_path.mkdir(parents=True, exist_ok=True)

    results = {"successful": [], "failed": []}
    common_tags_list = tags_str.split(',') if tags_str and tags_str.strip() else []

    for file in files:
        original_filename = file.filename or "unknown_file"
        file_location_on_disk = None # Initialize
        try:
            if file.content_type not in settings.ALLOWED_MIME_TYPES:
                results["failed"].append({"filename": original_filename, "error": f"Invalid MIME type (header): {file.content_type}. Allowed: {', '.join(settings.ALLOWED_MIME_TYPES)}"})
                continue

            file_content_chunk = await file.read(2048) # Read a chunk for magic
            await file.seek(0) # Reset file pointer
            true_mime_type = magic.from_buffer(file_content_chunk, mime=True)

            if true_mime_type not in settings.ALLOWED_MIME_TYPES:
                results["failed"].append({"filename": original_filename, "error": f"Invalid MIME type (content: {true_mime_type}). Allowed: {', '.join(settings.ALLOWED_MIME_TYPES)}"})
                continue
            
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            await file.seek(0) # Reset file pointer again for saving

            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                results["failed"].append({"filename": original_filename, "error": f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"})
                continue

            file_extension = Path(original_filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_location_on_disk = uploads_abs_path / unique_filename

            with open(file_location_on_disk, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)

            # Simple title/description for batch upload
            post_title = Path(original_filename).stem 
            post_description = f"Uploaded by admin: {original_filename}"

            post_data_create = models.PostCreate(
                filename=unique_filename,
                mimetype=true_mime_type,
                filesize=file_size,
                title=post_title,
                description=post_description,
                tags=common_tags_list
            )
            db_filepath = f"{settings.UPLOADS_DIR}/{unique_filename}" # Relative path for DB

            created_post_record = await crud.create_post_with_tags(
                db=db, redis=redis, post_data=post_data_create,
                filepath_on_disk=str(db_filepath), # Ensure it's a string
                uploader_id=current_user.id
            )

            if not created_post_record:
                if file_location_on_disk.exists(): os.remove(file_location_on_disk)
                results["failed"].append({"filename": original_filename, "error": "Could not create post record in database."})
                continue
            
            # Construct the response model for this successful upload
            created_post_record.image_url = get_admin_post_image_url(request, created_post_record.filename)
            created_post_record.thumbnail_url = created_post_record.image_url # Placeholder
            results["successful"].append(models.Post.model_validate(created_post_record).model_dump())

        except HTTPException as e: # Catch HTTPExceptions from validation steps
            if file_location_on_disk and file_location_on_disk.exists(): os.remove(file_location_on_disk)
            results["failed"].append({"filename": original_filename, "error": e.detail})
        except Exception as e:
            if file_location_on_disk and file_location_on_disk.exists(): os.remove(file_location_on_disk)
            results["failed"].append({"filename": original_filename, "error": f"An unexpected error occurred: {str(e)}"})
        finally:
            if hasattr(file, 'file') and file.file: # Ensure file object exists and is open
                file.file.close()
    
    if not results["successful"] and results["failed"]:
         # If all uploads failed, return a 400 or 500 level error
         # For simplicity, let's return 207 Multi-Status if there's a mix,
         # or 201 if all succeed, or an error if all fail.
         # This logic can be refined. If all fail, perhaps a 400 is more appropriate.
         # For now, let's assume if any failed, we still return 207 to show partial success/failure.
         # If ALL failed, maybe a 400 or 500 depending on why.
         # Let's adjust: if no successes, raise an error.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail={"message": "All file uploads failed.", "failures": results["failed"]}
        )

    # If there are any successes, even with failures, return 207 Multi-Status
    # If all were successful, 201 was already set.
    # FastAPI will override 201 with 200 if a response body is returned and status_code isn't explicitly set in return.
    # To ensure 207 for mixed results:
    if results["failed"]:
        # This requires a custom response or careful handling of status codes.
        # For now, let's return the results dict. The client can infer from it.
        # The status_code=201 is for "Created" if all are successful.
        # If there are failures, it's more like a "Multi-Status" (207).
        # However, FastAPI doesn't automatically switch to 207.
        # We'll return the dict, and the client can check 'failed' list.
        # If we want to strictly adhere to 207, we'd need to return a Response object.
        # For simplicity, we'll rely on the 201 if at least one succeeded.
        # The frontend will need to check the 'failed' array in the response.
        pass # Keep status_code 201 if at least one succeeded.

    return results # Returns a dict like {"successful": [...], "failed": [...]}


@router.put("/posts/batch-tags", status_code=status.HTTP_200_OK, tags=["Admin"])
async def batch_update_post_tags_admin(
    request_data: models.BatchTagUpdateRequest,
    current_user: Annotated[models.User, Depends(require_admin_owner)],
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    """
    Batch update tags for multiple posts. Admins/Owners only.
    Actions: add, remove, set.
    """
    if not request_data.post_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No post_ids provided.")
    
    # The Pydantic model BatchTagUpdateRequest already validates that tags list is not empty for add/remove.
    # For 'set' action, an empty tags list is allowed (to clear all tags).

    try:
        result = await crud.update_tags_for_posts(
            db=db,
            redis=redis,
            post_ids=request_data.post_ids,
            tag_names_to_modify=request_data.tags,
            action=request_data.action
        )
        
        if result.get("updated_posts_count", 0) == 0 and result.get("message") != "No post IDs provided.": # Check if posts were actually found and updated
             # If no posts were updated but some were targeted, it implies they weren't found or another issue.
             # The crud function returns a message if no valid post IDs or no existing posts are found.
            if "None of the provided post IDs exist" in result.get("message", ""):
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
            # For other cases where updated_posts_count is 0 but it's not due to "No post IDs provided" initially.
            # This could mean valid IDs were given, but none existed in DB.
            # The crud function already handles this by returning a specific message.
            # We can rely on the message from crud.

        return result
        
    except ValueError as ve: # Catch potential ValueErrors from crud or model validation
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        # Log the exception for server-side review
        print(f"Error during batch tag update: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred during batch tag update: {str(e)}")
