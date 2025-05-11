from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import asyncpg
import redis.asyncio as redis_async

from .. import crud, models
from ..core import security
from ..db import get_db_connection, get_redis_connection
from ..main import limiter

router = APIRouter(
    prefix="/posts/{post_id}/comments", # Nested under posts
    tags=["comments"],
)

@router.post("/", response_model=models.Comment, status_code=201)
async def create_new_comment( # Renamed for clarity
    post_id: int, # Now a path parameter due to prefix
    comment: models.CommentCreate,
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
    current_user: models.User = Depends(security.get_current_active_user),
):
    """
    Create a new comment on a specific post.
    """
    try:
        # Ensure post exists before attempting to add a comment
        target_post = await crud.get_post(db=db, redis=redis, post_id=post_id)
        if not target_post:
            raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found, cannot add comment.")

        created_comment = await crud.create_comment(
            db=db, redis=redis, comment_data=comment, post_id=post_id, user_id=current_user.id
        )
        return created_comment
    except Exception as e:
        # Log the exception e
        print(f"Error creating comment for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating comment: {str(e)}")

@router.get("/", response_model=List[models.Comment]) # Path is now relative to prefix
async def list_comments_for_post( # Renamed for clarity
    post_id: int, # Now a path parameter
    skip: int = 0,
    limit: int = 10,
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
):
    """
    Get comments for a specific post.
    """
    try:
        # Optional: Check if post exists first, though get_comments_for_post might return empty list if post has no comments
        # target_post = await crud.get_post(db=db, redis=redis, post_id=post_id)
        # if not target_post:
        #     raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found.")
            
        comments = await crud.get_comments_for_post(db=db, redis=redis, post_id=post_id, skip=skip, limit=limit)
        # If post exists but has no comments, an empty list is the correct response.
        # If crud.get_comments_for_post needs to differentiate "post not found" vs "post has no comments",
        # it should handle that, or we check post existence here.
        # For now, assume crud.get_comments_for_post returns empty list if post has no comments.
        return comments
    except Exception as e:
        # Log the exception e
        print(f"Error fetching comments for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching comments: {str(e)}")

# TODO: Add routes for:
# - Replying to a comment (e.g., POST /posts/{post_id}/comments/{comment_id}/replies/ or similar)
# - Updating a comment (e.g., PUT /posts/{post_id}/comments/{comment_id}/)
# - Deleting a comment (e.g., DELETE /posts/{post_id}/comments/{comment_id}/)
