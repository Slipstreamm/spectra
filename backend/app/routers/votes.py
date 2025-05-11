from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import asyncpg
import redis.asyncio as redis_async

from .. import crud, models
# from ..core import security # No longer needed for get_current_active_user here
from .auth import get_current_active_user # Import from auth router
from ..db import get_db_connection, get_redis_connection
from ..main import limiter

router = APIRouter(
    prefix="/votes",
    tags=["votes"],
    dependencies=[Depends(get_current_active_user)], # Voting generally requires auth, use imported dependency
)

@router.post("/", response_model=Optional[models.Vote], status_code=200) # Status 200 for update/delete, 201 for new
async def cast_or_update_vote(
    vote_in: models.VoteCreate,
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection),
    current_user: models.User = Depends(get_current_active_user), # Use imported dependency
):
    """
    Cast, update, or remove a vote on a post or a comment.
    Returns the vote object if created/updated, or null if removed (unvoted).
    """
    try:
        # Validate that the target post or comment exists
        if vote_in.post_id:
            target_post = await crud.get_post(db=db, redis=redis, post_id=vote_in.post_id)
            if not target_post:
                raise HTTPException(status_code=404, detail=f"Post with id {vote_in.post_id} not found.")
        elif vote_in.comment_id:
            # TODO: Implement crud.get_comment(comment_id) and use it here for validation
            # For now, we'll rely on the DB constraint or assume comment exists if vote_in.comment_id is provided.
            # This should be improved by fetching the comment to ensure it exists.
            # Example:
            # target_comment = await crud.get_comment_by_id(db=db, redis=redis, comment_id=vote_in.comment_id)
            # if not target_comment:
            #     raise HTTPException(status_code=404, detail=f"Comment with id {vote_in.comment_id} not found.")
            pass

        vote_result = await crud.cast_vote(
            db=db, redis=redis, vote_data=vote_in, user_id=current_user.id
        )
        
        # If vote_result is None, it means an existing vote was removed (unvoted).
        # FastAPI will correctly return `null` in the JSON response for Optional[models.Vote]
        # if vote_result is None. A 204 No Content might also be appropriate for deletion.
        # For simplicity, returning 200 with null body for unvote is acceptable.
        # If a new vote was created, status 201 might be more semantically correct.
        # However, this endpoint handles create, update, and delete.
        # A single 200 OK for all successful outcomes is simpler.
        return vote_result
        
    except ValueError as ve: # Catches Pydantic validation errors from VoteCreate or other ValueErrors
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        print(f"Error during vote casting: {e}")
        raise HTTPException(status_code=500, detail=f"Error casting vote: {str(e)}")

# TODO: Add routes to get votes for a post/comment, or user's votes, if needed.
