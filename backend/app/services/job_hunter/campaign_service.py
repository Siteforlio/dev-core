# backend/app/services/job_hunter/campaign_service.py
import uuid, json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobHunterCampaign, JobHunterProfile
from app.core.config import settings

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_haiku(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

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

    async def create_campaign(self, user_id: str, name: str, broad_category: str,
                               user_country: str, profile_overrides: dict | None = None) -> JobHunterCampaign:
        result = await self.db.execute(
            select(JobHunterProfile).where(JobHunterProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if not profile or not profile.is_complete:
            raise ValueError("Profile incomplete — complete all required fields before creating a campaign")

        sub_cats = await self.infer_sub_categories(
            skills=profile.skills or [], broad_category=broad_category
        )
        campaign = JobHunterCampaign(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            status="active",
            broad_category=broad_category,
            sub_categories=sub_cats,
            profile_overrides=profile_overrides or {},
            user_country=user_country.upper()[:2],
            email_monitor_since=utcnow(),
        )
        self.db.add(campaign)
        await self.db.commit()
        return campaign

    async def list_campaigns(self, user_id: str) -> list[JobHunterCampaign]:
        result = await self.db.execute(
            select(JobHunterCampaign).where(
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def set_status(self, campaign_id: str, status: str) -> None:
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one()
        campaign.status = status
        await self.db.commit()
