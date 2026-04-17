from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, TokenResponse
from app.services.auth_service import AuthService
from app.core.database import get_db
from app.core.security import decode_token, create_access_token
from app.core.exceptions import InvalidCredentialsError

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
        user_id = decode_token(credentials.credentials)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return {"data": {"access_token": create_access_token(user_id)}, "error": None}


@router.delete("/users/me", status_code=204)
async def delete_account(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """GDPR right-to-erasure: permanently delete the authenticated user's account."""
    service = AuthService(db=db)
    await service.delete_user(user_id=user_id)
