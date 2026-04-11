from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.job_hunter.dashboard_service import DashboardService

router = APIRouter(prefix="/job-hunter/campaigns", tags=["job-hunter-dashboard"])
bearer = HTTPBearer()


def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/{campaign_id}/dashboard", response_model=dict)
async def get_dashboard(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = DashboardService(db)
    summary = await service.get_campaign_summary(campaign_id, user_id)
    pipeline = await service.get_pipeline(campaign_id, user_id)
    interviews = await service.get_scheduled_interviews(campaign_id, user_id)
    return {"data": {"summary": summary, "pipeline": pipeline, "interviews": interviews}, "error": None}
