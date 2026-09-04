"""Apply worker — plain asyncio, no Celery."""
import logging
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def submit_application(application_id: str, board_id: str | None = None) -> dict:
    """
    Submit a job application.

    If board_id is provided, routes to the per-board applier (new path).
    Falls back to the original universal submit_application() when board_id is None.
    """
    from app.services.job_hunter.apply_service import ApplyService
    from app.models.pg.job_hunter import Application
    from app.core.config import get_api_key
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Application.user_id).where(Application.id == application_id))
        user_id = result.scalar_one_or_none() or ""
        api_key = await get_api_key(user_id, "deepseek_api_key", db) if user_id else ""
        service = ApplyService(db, api_key=api_key)
        if board_id:
            success = await service.submit_application_for_board(application_id, board_id)
        else:
            success = await service.submit_application(application_id)
        return {"success": success}
