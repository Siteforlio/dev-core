"""Scraper worker — plain asyncio, no Celery."""
import logging
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def scrape_campaign(campaign_id: str, user_id: str) -> dict:
    from app.services.job_hunter.scraper_service import ScraperService
    from app.core.config import get_api_key
    async with AsyncSessionLocal() as db:
        api_key = await get_api_key(user_id, "deepseek_api_key", db)
        service = ScraperService(db, api_key=api_key)
        count = await service.scrape_campaign(campaign_id, user_id)
        return {"scraped": count}

async def scrape_all_active_campaigns() -> None:
    from sqlalchemy import select
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.core.task_runner import get_runner
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobHunterCampaign).where(JobHunterCampaign.status == "active")
        )
        campaigns = result.scalars().all()
    runner = get_runner()
    for c in campaigns:
        runner.submit(scrape_campaign(c.id, c.user_id))
    logger.info("[scraper] queued %d campaigns", len(campaigns))
