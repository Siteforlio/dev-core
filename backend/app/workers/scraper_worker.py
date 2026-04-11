# backend/app/workers/scraper_worker.py
import asyncio
from app.core.celery_app import celery_app

@celery_app.task(name="app.workers.scraper_worker.scrape_campaign")
def scrape_campaign(campaign_id: str, user_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.scraper_service import ScraperService
    async def _run():
        async with AsyncSessionLocal() as db:
            service = ScraperService(db)
            count = await service.scrape_campaign(campaign_id, user_id)
            return {"scraped": count}
    return asyncio.run(_run())

@celery_app.task(name="app.workers.scraper_worker.scrape_all_active_campaigns")
def scrape_all_active_campaigns() -> None:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.pg.job_hunter import JobHunterCampaign
    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(JobHunterCampaign).where(JobHunterCampaign.status == "active")
            )
            campaigns = result.scalars().all()
            for c in campaigns:
                scrape_campaign.delay(c.id, c.user_id)
    asyncio.run(_run())
