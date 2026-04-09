from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, TokenResponse
from app.services.auth_service import AuthService
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


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
