from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import Application, JobListing
from app.services.persona_engine import PersonaEngine


class BridgeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._persona_engine = PersonaEngine()

    async def get_interview_context(self, application_id: str, campaign_id: str | None = None) -> dict:
        query = (
            select(Application, JobListing)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.id == application_id)
        )
        if campaign_id:
            query = query.where(Application.campaign_id == campaign_id)
        result = await self.db.execute(query)
        row = result.first()
        if not row:
            return {}
        application, listing = row
        context = await self._persona_engine.get_context(
            company=listing.company,
            role=listing.title,
            round_type="HR",
        )
        return {
            **context,
            "company": listing.company,
            "role": listing.title,
            "application_id": application_id,
        }
