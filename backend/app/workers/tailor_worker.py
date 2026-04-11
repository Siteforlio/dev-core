# backend/app/workers/tailor_worker.py
import asyncio
from app.core.celery_app import celery_app

@celery_app.task(
    name="app.workers.tailor_worker.tailor_listing",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
)
def tailor_listing(self, listing_id: str, user_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.tailor_service import TailorService
    async def _run():
        async with AsyncSessionLocal() as db:
            service = TailorService(db)
            app = await service.tailor_for_listing(listing_id, user_id)
            return {"application_id": app.id if app else None}
    return asyncio.run(_run())
