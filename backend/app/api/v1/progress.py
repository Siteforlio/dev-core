# backend/app/api/v1/progress.py
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress", tags=["progress"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/me")
async def get_my_progress(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = ProgressService(db=db)
    summary = await svc.get_summary(user_id=user_id)
    return {"data": summary, "error": None}
