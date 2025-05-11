from fastapi import APIRouter, Depends, HTTPException
from typing import List
import asyncpg
import redis.asyncio as redis_async

from .. import crud, models
from ..db import get_db_connection, get_redis_connection
from ..main import limiter # Assuming limiter is accessible from main

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
)

@router.get("/", response_model=List[models.TagWithCount])
@limiter.limit("30/minute") # Example rate limit
async def list_all_tags_with_counts(
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: redis_async.Redis = Depends(get_redis_connection)
):
    """
    Retrieve all tags with their associated post counts.
    """
    try:
        tags_with_counts = await crud.get_all_tags_with_counts(db=db, redis=redis)
        return tags_with_counts
    except Exception as e:
        # Log the exception e
        print(f"Error fetching all tags with counts: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve tags.")
