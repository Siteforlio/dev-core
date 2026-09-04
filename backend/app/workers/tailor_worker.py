"""Tailor worker — plain asyncio, no Celery."""
import logging
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def tailor_listing(listing_id: str, user_id: str) -> dict:
    from app.services.job_hunter.tailor_service import TailorService
    from app.core.config import get_api_key
    async with AsyncSessionLocal() as db:
        api_key = await get_api_key(user_id, "deepseek_api_key", db)
        service = TailorService(db, api_key=api_key)
        app_obj = await service.tailor_for_listing(listing_id, user_id)
        return {"application_id": app_obj.id if app_obj else None}
