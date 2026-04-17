from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.job_hunter import Application, CalendarEvent, CampaignActivityLog, JobHunterCampaign, JobListing


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _owned_campaign_subquery(self, campaign_id: str, user_id: str):
        """Return a subquery that verifies the campaign belongs to the user."""
        return (
            select(JobHunterCampaign.id)
            .where(
                JobHunterCampaign.id == campaign_id,
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
            )
            .scalar_subquery()
        )

    async def get_campaign_summary(self, campaign_id: str, user_id: str) -> dict:
        owned = self._owned_campaign_subquery(campaign_id, user_id)
        total = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == owned
            )
        )).scalar()
        interviews = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == owned, Application.status == "interview"
            )
        )).scalar()
        rejections = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == owned, Application.status == "rejected"
            )
        )).scalar()
        offers = (await self.db.execute(
            select(func.count()).select_from(Application).where(
                Application.campaign_id == owned, Application.status == "offer"
            )
        )).scalar()
        return {
            "total_applications": total,
            "interviews": interviews,
            "rejections": rejections,
            "offers": offers,
        }

    async def get_pipeline(self, campaign_id: str, user_id: str) -> list[dict]:
        """Return all job listings for this campaign, with application status if one exists."""
        owned = self._owned_campaign_subquery(campaign_id, user_id)
        result = await self.db.execute(
            select(JobListing, Application)
            .outerjoin(Application, Application.job_listing_id == JobListing.id)
            .where(
                JobListing.campaign_id == owned,
                JobListing.deleted_at.is_(None),
            )
            .order_by(JobListing.discovered_at.desc())
            .limit(200)
        )
        return [
            {
                "id": listing.id,
                "status": app.status if app else listing.status,
                "discovered_at": listing.discovered_at.isoformat(),
                "applied_at": app.applied_at.isoformat() if app else None,
                "company": listing.company,
                "title": listing.title,
                "location": listing.location,
                "remote": listing.remote,
                "match_score": listing.match_score,
                "source": listing.source,
                "url": listing.url,
            }
            for listing, app in result.all()
        ]

    async def get_activity_log(self, campaign_id: str, user_id: str, limit: int = 200) -> list[dict]:
        owned = self._owned_campaign_subquery(campaign_id, user_id)
        result = await self.db.execute(
            select(CampaignActivityLog)
            .where(CampaignActivityLog.campaign_id == owned)
            .order_by(CampaignActivityLog.created_at.asc())
            .limit(limit)
        )
        return [
            {"message": log.message, "created_at": log.created_at.isoformat()}
            for log in result.scalars().all()
        ]

    async def get_scheduled_interviews(self, campaign_id: str, user_id: str) -> list[dict]:
        owned = self._owned_campaign_subquery(campaign_id, user_id)
        result = await self.db.execute(
            select(CalendarEvent, Application, JobListing)
            .join(Application, CalendarEvent.application_id == Application.id)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.campaign_id == owned)
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
