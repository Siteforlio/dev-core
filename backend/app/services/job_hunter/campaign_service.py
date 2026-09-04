# backend/app/services/job_hunter/campaign_service.py
import uuid, json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import JobHunterCampaign, JobHunterProfile
from app.core.config import settings
from app.services.job_hunter.llm import call_llm

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class CampaignService:
    def __init__(self, db: AsyncSession, api_key: str = ""):
        self._api_key = api_key
        self.db = db

    async def _call_haiku(self, prompt: str) -> str:
        return await call_llm(prompt, self._api_key, max_tokens=500)

    async def infer_sub_categories(self, skills: list[str], broad_category: str) -> list[str]:
        prompt = (
            f"Given these skills: {', '.join(skills)} and broad job category: '{broad_category}', "
            f"return a JSON array of specific job sub-categories this person can apply to. "
            f"Examples: Mobile Development, Backend Engineering, Full Stack, DevOps. Max 5 items. JSON array only."
        )
        raw = await self._call_haiku(prompt)
        try:
            start, end = raw.find("["), raw.rfind("]") + 1
            if start == -1 or end == 0:
                return []
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return []

    async def create_campaign(
        self,
        user_id: str,
        name: str,
        broad_category: str,
        sub_categories: list[str] | None = None,
        user_country: str | None = None,
        anywhere: bool = False,
        work_type: str = "remote",
        work_types: list[str] | None = None,
        profile_overrides: dict | None = None,
    ) -> JobHunterCampaign:
        campaign = JobHunterCampaign(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            status="active",
            broad_category=broad_category,
            sub_categories=sub_categories or [],
            profile_overrides=profile_overrides or {},
            user_country=(user_country or "").upper() if user_country else None,
            anywhere=anywhere,
            work_type=work_type,
            work_types=work_types,
            email_monitor_since=utcnow(),
        )
        self.db.add(campaign)
        await self.db.commit()
        return campaign

    async def infer_sub_categories_from_profile(self, campaign_id: str) -> list[str]:
        """Call after campaign profile has skills — infers sub-categories."""
        from app.models.pg.job_hunter import CampaignProfile
        profile_result = await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == campaign_id)
        )
        profile = profile_result.scalar_one_or_none()
        campaign_result = await self.db.execute(
            select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if not profile or not campaign:
            return []
        sub_cats = await self.infer_sub_categories(profile.skills or [], campaign.broad_category)
        campaign.sub_categories = sub_cats
        await self.db.commit()
        return sub_cats

    async def list_campaigns(self, user_id: str) -> list[JobHunterCampaign]:
        result = await self.db.execute(
            select(JobHunterCampaign).where(
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def delete_campaign(self, campaign_id: str, user_id: str) -> None:
        from datetime import datetime, timezone
        result = await self.db.execute(
            select(JobHunterCampaign).where(
                JobHunterCampaign.id == campaign_id,
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise ValueError("Campaign not found")
        campaign.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.commit()

    async def set_status(self, campaign_id: str, user_id: str, status: str) -> None:
        result = await self.db.execute(
            select(JobHunterCampaign).where(
                JobHunterCampaign.id == campaign_id,
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise ValueError("Campaign not found")
        campaign.status = status
        await self.db.commit()
