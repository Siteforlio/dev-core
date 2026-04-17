# backend/app/workers/apply_worker.py
import asyncio
from sqlalchemy.exc import OperationalError
from app.core.celery_app import celery_app

import app.models.pg.user  # noqa: F401
import app.models.pg.session  # noqa: F401
import app.models.pg.job_hunter  # noqa: F401


def _make_session():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings
    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, expire_on_commit=False), engine


@celery_app.task(
    name="app.workers.apply_worker.submit_application",
    bind=True,
    autoretry_for=(OperationalError,),
    max_retries=3,
    default_retry_delay=60,
)
def submit_application(self, application_id: str) -> dict:
    from app.services.job_hunter.apply_service import ApplyService

    async def _run():
        Session, engine = _make_session()
        try:
            async with Session() as db:
                service = ApplyService(db)
                success = await service.submit_application(application_id)
                return {"success": success}
        finally:
            await engine.dispose()

    return asyncio.run(_run())
