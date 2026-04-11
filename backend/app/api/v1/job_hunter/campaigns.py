# backend/app/api/v1/job_hunter/campaigns.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.job_hunter.campaign_service import CampaignService
from app.schemas.job_hunter import CampaignCreateRequest, CampaignStatusRequest

router = APIRouter(prefix="/job-hunter/campaigns", tags=["job-hunter-campaigns"])
bearer = HTTPBearer()

def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)

@router.post("", response_model=dict)
async def create_campaign(
    body: CampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = CampaignService(db)
    try:
        campaign = await service.create_campaign(
            user_id=user_id, name=body.name,
            broad_category=body.broad_category, user_country=body.user_country,
            profile_overrides=body.profile_overrides,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"data": {"id": campaign.id, "name": campaign.name, "status": campaign.status,
                     "sub_categories": campaign.sub_categories}, "error": None}

@router.get("", response_model=dict)
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = CampaignService(db)
    campaigns = await service.list_campaigns(user_id)
    return {"data": [{"id": c.id, "name": c.name, "status": c.status,
                      "sub_categories": c.sub_categories, "broad_category": c.broad_category} for c in campaigns], "error": None}

@router.patch("/{campaign_id}/status", response_model=dict)
async def update_status(
    campaign_id: str,
    body: CampaignStatusRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = CampaignService(db)
    try:
        await service.set_status(campaign_id, user_id, body.status)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"data": {"updated": True}, "error": None}
