from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import settings
from .. import crud, models # Corrected relative import
from ..db import get_db_connection # Corrected relative import
import asyncpg # For type hinting

# OAuth2PasswordBearer scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token") # tokenUrl points to your login endpoint

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.security.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.security.secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.security.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: asyncpg.Connection = Depends(get_db_connection) # Add db dependency
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = await crud.get_user_by_username(db, username=username) # Use await for async CRUD
    if user is None:
        raise credentials_exception
    # Ensure the User model is correctly instantiated.
    # UserInDB has 'role', User model (via UserBase) also has 'role'.
    # is_superuser in User model defaults to False. If it needs to be derived from role for this specific model instance:
    # user_data = user.model_dump()
    # user_data['is_superuser'] = user.role in [models.UserRole.admin, models.UserRole.owner]
    # return models.User(**user_data)
    # However, the User model itself should handle its fields correctly based on UserBase.
    return models.User.model_validate(user) # Use model_validate for direct conversion if fields align

# The following functions are now handled by `auth.py` and its role-based dependencies.
# async def get_current_active_user(
#     current_user: models.User = Depends(get_current_user)
# ) -> models.User:
#     if not current_user.is_active:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
#     return current_user

# async def get_current_active_superuser(
#     current_user: models.User = Depends(get_current_active_user)
# ) -> models.User:
#     # This function is outdated due to the new role system.
#     # Role-based checks are now preferred (e.g., require_role in auth.py).
#     if not current_user.is_superuser: # is_superuser might be False by default in User model
#         # and should be derived from role if still used.
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges"
#         )
#     return current_user
