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
    async with AsyncSessionLocal() as db:
        service = ApplyService(db)
        if board_id:
            success = await service.submit_application_for_board(application_id, board_id)
        else:
            success = await service.submit_application(application_id)
        return {"success": success}
