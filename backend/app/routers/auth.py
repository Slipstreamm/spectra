from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
import asyncpg
from datetime import timedelta # Ensure timedelta is imported

from .. import models, crud # Corrected import path
from ..core import security # Corrected import path
from ..db import get_db_connection # Corrected import path and function name
from ..core.config import settings # Corrected import path

router = APIRouter()

class Token(models.BaseModel):
    access_token: str
    token_type: str

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

async def get_current_user_from_token(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: asyncpg.Connection = Depends(get_db_connection) # Use correct DB dependency
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = security.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user_in_db = await crud.get_user_by_username(db, username=username)
    if user_in_db is None:
        raise credentials_exception
    # Return as User model (without hashed_password)
    return models.User.model_validate(user_in_db)

async def get_current_active_user(
    current_user: Annotated[models.User, Depends(get_current_user_from_token)]
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user") # Changed to 401 for consistency
    return current_user

async def get_current_active_superuser(
    current_user: Annotated[models.User, Depends(get_current_active_user)]
) -> models.User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges" # Changed to 403
        )
    return current_user


@router.post("/token", response_model=Token, tags=["Authentication"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: asyncpg.Connection = Depends(get_db_connection) # Use correct DB dependency
):
    user = await crud.get_user_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=models.User, tags=["Users"])
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_active_user)]
):
    """
    Get current logged-in user.
    """
    return current_user

# Example of a superuser-only endpoint (can be expanded in an admin router)
@router.get("/users/me/superuser-test", response_model=models.User, tags=["Users"])
async def read_superuser_me(
    current_user: Annotated[models.User, Depends(get_current_active_superuser)]
):
    """
    Test endpoint for superuser access.
    """
    return current_user
