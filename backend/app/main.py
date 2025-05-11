from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse # Added for custom rate limit response
import asyncpg
import redis.asyncio as redis
import os
from slowapi import Limiter, _rate_limit_exceeded_handler # Added slowapi
from slowapi.util import get_remote_address # Changed to get_remote_address, will customize
from slowapi.errors import RateLimitExceeded # Added
from slowapi.middleware import SlowAPIMiddleware # Added

from .core.config import settings
# We will define db connection functions in db.py and import them or use dependencies

# Custom key function to get IP from X-Real-IP or fallback to remote address
def get_request_identifier(request: Request) -> str:
    # Try to get the IP from X-Real-IP header
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip
    # Fallback to the direct client address if header is not present
    return get_remote_address(request)

limiter = Limiter(key_func=get_request_identifier, default_limits=[settings.security.default_rate_limit])

app = FastAPI(title=settings.site.name) # Use site name from config
app.state.limiter = limiter # Add limiter to app state
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # Handle rate limit exceeded
app.add_middleware(SlowAPIMiddleware) # Add SlowAPI middleware

# Database and Redis connection pools will be stored in app.state
# app.state.pg_pool = None
# app.state.redis_pool = None

@app.on_event("startup")
async def startup_event():
    """
    Application startup:
    - Create PostgreSQL connection pool.
    - Create Redis connection pool.
    - Create uploads directory if it doesn't exist.
    """
    try:
        app.state.pg_pool = await asyncpg.create_pool(
            str(settings.DATABASE_URL),  # Ensure DATABASE_URL is a string
            min_size=5,
            max_size=20
        )
        print("PostgreSQL connection pool created.")
    except Exception as e:
        print(f"Error creating PostgreSQL connection pool: {e}")
        # Optionally, re-raise or handle critical failure
        raise

    try:
        app.state.redis_pool = redis.ConnectionPool.from_url(
            str(settings.REDIS_URL) # Ensure REDIS_URL is a string
        )
        # To test the redis connection, you might try to ping
        # r = redis.Redis(connection_pool=app.state.redis_pool)
        # await r.ping()
        # await r.close()
        print("Redis connection pool created.")
    except Exception as e:
        print(f"Error creating Redis connection pool: {e}")
        # Optionally, re-raise or handle critical failure
        raise

    # Create uploads directory if it doesn't exist
    # UPLOADS_DIR is relative to project root, ensure correct path resolution
    # For StaticFiles, the path should be relative to where main.py is if not absolute
    # settings.UPLOADS_DIR is "backend/uploads"
    # If main.py is in backend/app, then ../uploads might be needed if StaticFiles resolves from app dir
    # However, FastAPI StaticFiles path is usually relative to the CWD or an absolute path.
    # Let's assume settings.UPLOADS_DIR is correctly defined relative to the project root.
    
    # Construct absolute path for uploads_dir if it's relative
    # Project root is z:/projects_git/spectra
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # spectra/
    uploads_abs_path = os.path.join(project_root, settings.UPLOADS_DIR)
    
    if not os.path.exists(uploads_abs_path):
        os.makedirs(uploads_abs_path)
        print(f"Uploads directory created at: {uploads_abs_path}")
    
    # Mount static files for uploads
    # The path "/static/uploads" will be the URL path
    # The directory is settings.UPLOADS_DIR
    # Ensure StaticFiles uses an absolute path or a path relative to where the app is run.
    # If UPLOADS_DIR is "backend/uploads", and app is run from "spectra/"
    # then "backend/uploads" is correct.
    app.mount(f"{settings.API_V1_STR}/static/uploads", StaticFiles(directory=uploads_abs_path, html=False), name="static_uploads")
    print(f"Static files mounted at {settings.API_V1_STR}/static/uploads, serving from {uploads_abs_path}")

    # Mount static files for frontend
    # project_root is already defined above in this function
    frontend_abs_path = os.path.join(project_root, "frontend")
    app.mount("/", StaticFiles(directory=frontend_abs_path, html=True), name="static_frontend")
    print(f"Static frontend mounted at /, serving from {frontend_abs_path}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown:
    - Close PostgreSQL connection pool.
    - Close Redis connection pool.
    """
    if hasattr(app.state, 'pg_pool') and app.state.pg_pool:
        await app.state.pg_pool.close()
        print("PostgreSQL connection pool closed.")
    
    if hasattr(app.state, 'redis_pool') and app.state.redis_pool:
        # For redis.asyncio ConnectionPool, explicit closing is not typically needed
        # as connections are managed. If you created a client instance, you'd close that.
        # await app.state.redis_pool.disconnect() # if it were a client
        print("Redis connection pool resources released (if applicable).")

# Further imports and API routers will be added here.
from .routers import posts, auth, admin, utils, comments, votes, tags # Import new routers

app.include_router(posts.router, prefix=settings.API_V1_STR, tags=["Posts"])
app.include_router(auth.router, prefix=settings.API_V1_STR + "/auth", tags=["Authentication"])
app.include_router(admin.router, prefix=settings.API_V1_STR + "/admin", tags=["Admin"])
app.include_router(utils.router, prefix=settings.API_V1_STR, tags=["Utils"])
app.include_router(comments.router, prefix=settings.API_V1_STR, tags=["Comments"]) # Added comments router
app.include_router(votes.router, prefix=settings.API_V1_STR, tags=["Votes"]) # Added votes router
app.include_router(tags.router, prefix=settings.API_V1_STR, tags=["Tags"]) # Include tags router
