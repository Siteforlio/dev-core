# backend/app/workers/email_worker.py
import asyncio
from sqlalchemy.exc import OperationalError
from app.core.celery_app import celery_app


@celery_app.task(
    name="app.workers.email_worker.poll_all_campaigns",
    bind=True,
    autoretry_for=(OperationalError,),
    max_retries=3,
    default_retry_delay=30,
)
def poll_all_campaigns(self) -> None:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(JobHunterCampaign).where(
                    JobHunterCampaign.status == "active",
                    JobHunterCampaign.email_account_encrypted.isnot(None),
                )
            )
            campaigns = result.scalars().all()
            for c in campaigns:
                service = EmailService(db)
                await service.process_campaign_emails(c.id)

    asyncio.run(_run())
