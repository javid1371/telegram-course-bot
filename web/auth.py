"""
JWT Authentication for Web Admin Panel
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# Config
SECRET_KEY = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "change-me-in-production"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

# Admin credentials from env
ADMIN_USERNAME = os.getenv("ADMIN_WEB_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_WEB_PASSWORD", "")

security = HTTPBearer()


class TokenData(BaseModel):
    username: str
    exp: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str


def create_access_token(username: str) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expires}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires


def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        exp = payload.get("exp")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return TokenData(username=username, exp=datetime.fromtimestamp(exp, tz=timezone.utc))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    return verify_token(credentials.credentials)


def authenticate_user(username: str, password: str) -> bool:
    """Verify admin credentials."""
    if not ADMIN_PASSWORD:
        # No password set — reject all logins
        return False
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
