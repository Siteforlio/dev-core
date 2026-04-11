from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.job_hunter.profile_service import ProfileService
from app.schemas.job_hunter import ProfileUpsertRequest, ResumeTextRequest

router = APIRouter(prefix="/job-hunter/profiles", tags=["job-hunter-profiles"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.put("/me", response_model=dict)
async def upsert_profile(
    body: ProfileUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = ProfileService(db)
    profile = await service.upsert_profile(user_id, body.model_dump())
    completeness = service.check_completeness(body.model_dump())
    return {
        "data": {
            "id": profile.id,
            "is_complete": profile.is_complete,
            "completion_score": profile.completion_score,
            "missing_fields": completeness["missing"],
        },
        "error": None,
    }


@router.post("/me/parse-resume", response_model=dict)
async def parse_resume(
    body: ResumeTextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = ProfileService(db)
    extracted = await service.parse_resume_text(body.text)
    return {"data": extracted, "error": None}
