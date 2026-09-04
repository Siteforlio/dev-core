"""Email worker — plain asyncio, no Celery."""
import logging
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def poll_all_campaigns() -> None:
    from sqlalchemy import select
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService
    from app.core.config import get_api_key

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobHunterCampaign).where(
                JobHunterCampaign.status == "active",
                JobHunterCampaign.email_account_encrypted.isnot(None),
            )
        )
        campaigns = result.scalars().all()
        for c in campaigns:
            api_key = await get_api_key(c.user_id, "deepseek_api_key", db)
            service = EmailService(db, api_key=api_key)
            await service.process_campaign_emails(c.id)
