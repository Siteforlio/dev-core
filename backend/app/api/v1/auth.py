from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, TokenResponse
from app.services.auth_service import AuthService
from app.core.database import get_db
from app.core.security import decode_token, create_access_token, create_refresh_token, decode_refresh_token_payload
from app.core.cache import blacklist_jti, is_jti_blacklisted
from app.core.exceptions import InvalidCredentialsError
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db=db)
    user = await service.register(**body.model_dump())
    tokens = await service.login(email=body.email, password=body.password)
    return {"data": TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user_id=user.id,
        name=user.name,
        language_pref=user.language_pref,
    )}


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db=db)
    result = await service.login(email=body.email, password=body.password)
    return {"data": TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user_id=result["user"].id,
        name=result["user"].name,
        language_pref=result["user"].language_pref,
    )}


@router.post("/refresh", response_model=dict)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload = decode_refresh_token_payload(credentials.credentials)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    jti = payload.get("jti")
    user_id: str = payload["sub"]

    # Replay attack check: reject if this JTI was already used
    if jti and await is_jti_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Refresh token already used")

    # Issue new tokens
    new_access  = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    # Blacklist the old refresh token JTI for its remaining lifetime
    if jti:
        exp = payload.get("exp")
        if exp:
            remaining_ttl = int(exp - datetime.now(timezone.utc).timestamp())
        else:
            remaining_ttl = settings.jwt_refresh_expire_days * 86400
        await blacklist_jti(jti, max(remaining_ttl, 1))

    return {"data": {"access_token": new_access, "refresh_token": new_refresh}, "error": None}


@router.delete("/users/me", status_code=204)
async def delete_account(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """GDPR right-to-erasure: permanently delete the authenticated user's account."""
    service = AuthService(db=db)
    await service.delete_user(user_id=user_id)
