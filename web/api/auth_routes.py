"""
Auth API Routes
"""
from fastapi import APIRouter, HTTPException, Depends

from web.auth import (
    LoginRequest,
    TokenResponse,
    authenticate_user,
    create_access_token,
    get_current_user,
    TokenData,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    if not authenticate_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")
    token, expires = create_access_token(req.username)
    return TokenResponse(access_token=token, expires_at=expires.isoformat())


@router.get("/me")
async def me(user: TokenData = Depends(get_current_user)):
    return {"username": user.username, "expires_at": user.exp.isoformat()}
