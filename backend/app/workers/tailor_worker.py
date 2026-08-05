"""Tailor worker — plain asyncio, no Celery."""
import logging
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def tailor_listing(listing_id: str, user_id: str) -> dict:
    from app.services.job_hunter.tailor_service import TailorService
    async with AsyncSessionLocal() as db:
        service = TailorService(db)
        app_obj = await service.tailor_for_listing(listing_id, user_id)
        return {"application_id": app_obj.id if app_obj else None}
