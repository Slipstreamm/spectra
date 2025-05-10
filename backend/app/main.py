from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
import asyncpg
import redis.asyncio as redis
import os

from .core.config import settings
# We will define db connection functions in db.py and import them or use dependencies

app = FastAPI(title=settings.PROJECT_NAME)

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


@app.get("/")
async def read_root(request: Request):
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs_url": request.url_for("swagger_ui_html"),
        "redoc_url": request.url_for("redoc_html"),
        "pg_pool_status": "Created" if hasattr(app.state, 'pg_pool') and app.state.pg_pool else "Not created",
        "redis_pool_status": "Created" if hasattr(app.state, 'redis_pool') and app.state.redis_pool else "Not created",
    }

# Further imports and API routers will be added here.
from .routers import images #, tags # Import tags router when created

app.include_router(images.router, prefix=settings.API_V1_STR, tags=["Images"])
# app.include_router(tags.router, prefix=settings.API_V1_STR, tags=["Tags"]) # Include tags router when created
