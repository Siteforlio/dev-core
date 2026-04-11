# backend/app/workers/apply_worker.py
import asyncio
from anthropic import APITimeoutError, APIConnectionError
from app.core.celery_app import celery_app

@celery_app.task(
    name="app.workers.apply_worker.submit_application",
    bind=True,
    autoretry_for=(APITimeoutError, APIConnectionError),
    max_retries=3,
    default_retry_delay=60,
)
def submit_application(self, application_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.apply_service import ApplyService
    async def _run():
        async with AsyncSessionLocal() as db:
            service = ApplyService(db)
            success = await service.submit_application(application_id)
            return {"success": success}
    return asyncio.run(_run())
