from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import Annotated, List
import asyncpg
from datetime import timedelta

from .. import models, crud
from ..core import security
from ..db import get_db_connection
from ..core.config import settings
from ..models import UserRole # Import UserRole

router = APIRouter()

# Removed class Token(models.BaseModel) as it's defined in models.py
# class Token(models.BaseModel):
#     access_token: str
#     token_type: str

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
    
    user_in_db = await crud.get_user_by_username(db, username=username) # Returns UserInDB
    if user_in_db is None:
        raise credentials_exception
    
    # Construct models.User from models.UserInDB
    # UserInDB has 'role' and 'hashed_password'. User model has 'role' (from UserBase)
    # and 'is_superuser' (defaults to False, can be derived from role if needed for response).
    user_data = user_in_db.model_dump(exclude={"hashed_password"})
    
    # Explicitly set is_superuser based on role for the response model if desired
    # user_data['is_superuser'] = user_in_db.role in [UserRole.admin, UserRole.owner]

    return models.User(**user_data)

async def get_current_active_user(
    current_user: Annotated[models.User, Depends(get_current_user_from_token)]
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user

# Role-based access control dependencies
def require_role(required_roles: List[UserRole]):
    async def role_checker(current_user: Annotated[models.User, Depends(get_current_active_user)]) -> models.User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have the required role(s): {', '.join(r.value for r in required_roles)}"
            )
        return current_user
    return role_checker

# Specific role dependencies (examples)
require_admin_owner = require_role([UserRole.admin, UserRole.owner])
require_moderator_admin_owner = require_role([UserRole.moderator, UserRole.admin, UserRole.owner])
require_owner = require_role([UserRole.owner])


@router.post("/token", response_model=models.Token, tags=["Authentication"]) # Use models.Token
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user = await crud.get_user_by_username(db, username=form_data.username) # Returns UserInDB
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active: # UserInDB has is_active
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.security.access_token_expire_minutes)
    access_token = security.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=models.User, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register_user(
    user_in: models.UserCreate,
    db: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Create new user.
    """
    db_user_email = await crud.get_user_by_email(db, email=user_in.email)
    if db_user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    db_user_username = await crud.get_user_by_username(db, username=user_in.username)
    if db_user_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this username already exists.",
        )
    
    # UserCreate model now defaults role to 'user'
    # user_in.role = UserRole.user # Ensure default role if not set by model
    
    try:
        created_user = await crud.create_user(db=db, user_in=user_in)
    except ValueError as e: # Catch potential errors from crud.create_user if any (though checks are above)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return created_user


@router.get("/users/me", response_model=models.User, tags=["Users"])
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_active_user)]
):
    """
    Get current logged-in user.
    """
    return current_user

# Example of a superuser-only endpoint (can be expanded in an admin router)
# This will now use role-based dependency
@router.get("/users/me/admin-test", response_model=models.User, tags=["Users"], dependencies=[Depends(require_admin_owner)])
async def read_admin_me(
    current_user: Annotated[models.User, Depends(get_current_active_user)] # current_user is already validated by require_admin_owner
):
    """
    Test endpoint for admin/owner access.
    """
    return current_user
