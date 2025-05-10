from fastapi import Request
import asyncpg
import redis.asyncio as redis
# from .core.config import settings # settings might not be directly needed here anymore

# Database connection dependency
async def get_db_connection(request: Request) -> asyncpg.Connection:
    """
    FastAPI dependency to get a PostgreSQL connection from the pool
    stored in app.state.
    """
    if not hasattr(request.app.state, 'pg_pool') or request.app.state.pg_pool is None:
        # This case should ideally be prevented by proper app startup
        raise RuntimeError("PostgreSQL connection pool not initialized.")
    
    # Acquire a connection from the pool
    conn: asyncpg.Connection = await request.app.state.pg_pool.acquire()
    try:
        yield conn  # Provide the connection to the route
    finally:
        # Release the connection back to the pool
        await request.app.state.pg_pool.release(conn)

# Redis connection dependency
async def get_redis_connection(request: Request) -> redis.Redis:
    """
    FastAPI dependency to get a Redis client instance using the connection pool
    stored in app.state.
    """
    if not hasattr(request.app.state, 'redis_pool') or request.app.state.redis_pool is None:
        # This case should ideally be prevented by proper app startup
        raise RuntimeError("Redis connection pool not initialized.")

    # Create a Redis client instance using the connection pool
    # The client will manage connections from the pool.
    r = redis.Redis(connection_pool=request.app.state.redis_pool)
    try:
        yield r # Provide the Redis client to the route
    finally:
        # For redis.asyncio, when using a connection pool,
        # the client itself doesn't need to be explicitly closed here
        # as the pool manages the connections.
        # If we were not using a pool or if the client had its own connection,
        # we would do: await r.close()
        pass
