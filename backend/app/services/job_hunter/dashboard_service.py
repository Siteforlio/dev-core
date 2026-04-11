from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.job_hunter import Application, EmailEvent, CalendarEvent, JobHunterCampaign, JobListing


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_campaign_summary(self, campaign_id: str) -> dict:
        total = (await self.db.execute(
            select(func.count()).select_from(Application).where(Application.campaign_id == campaign_id)
        )).scalar()
        interviews = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == campaign_id, Application.status == "interview"
            )
        )).scalar()
        rejections = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == campaign_id, Application.status == "rejected"
            )
        )).scalar()
        offers = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == campaign_id, Application.status == "offer"
            )
        )).scalar()
        return {
            "total_applications": total,
            "interviews": interviews,
            "rejections": rejections,
            "offers": offers,
        }

    async def get_pipeline(self, campaign_id: str) -> list[dict]:
        result = await self.db.execute(
            select(Application, JobListing)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.campaign_id == campaign_id)
            .order_by(Application.applied_at.desc())
            .limit(100)
        )
        return [
            {
                "application_id": app.id,
                "status": app.status,
                "applied_at": app.applied_at.isoformat(),
                "company": listing.company,
                "title": listing.title,
                "location": listing.location,
                "match_score": listing.match_score,
                "cover_letter": app.cover_letter,
            }
            for app, listing in result.all()
        ]

    async def get_scheduled_interviews(self, campaign_id: str) -> list[dict]:
        result = await self.db.execute(
            select(CalendarEvent, Application, JobListing)
            .join(Application, CalendarEvent.application_id == Application.id)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.campaign_id == campaign_id)
            .order_by(CalendarEvent.scheduled_at)
        )
        return [
            {
                "calendar_event_id": ce.id,
                "application_id": app.id,
                "title": ce.title,
                "scheduled_at": ce.scheduled_at.isoformat(),
                "duration_minutes": ce.duration_minutes,
                "company": listing.company,
                "role": listing.title,
            }
            for ce, app, listing in result.all()
        ]
