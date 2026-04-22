# backend/app/workers/tailor_worker.py
import asyncio
from anthropic import APITimeoutError, APIConnectionError, AnthropicError
from app.core.celery_app import celery_app

# Import ALL models so SQLAlchemy can resolve foreign keys across tables
# (Celery only imports what's needed — without this, FKs to `users` etc. fail)
import app.models.pg.user  # noqa: F401
import app.models.pg.session  # noqa: F401
import app.models.pg.job_hunter  # noqa: F401


def _make_session():
    """
    Create a fresh SQLAlchemy async engine + session bound to the current event loop.
    Must NOT share the module-level engine from app.core.database — asyncpg connections
    are loop-bound, and Celery's asyncio.run() creates a new loop each call.
    """
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
    name="app.workers.tailor_worker.tailor_listing",
    bind=True,
    autoretry_for=(APITimeoutError, APIConnectionError, AnthropicError),
    max_retries=5,
    default_retry_delay=65,  # 429 rate limits reset per minute
)
def tailor_listing(self, listing_id: str, user_id: str) -> dict:
    from app.services.job_hunter.tailor_service import TailorService

    async def _run():
        Session, engine = _make_session()
        try:
            async with Session() as db:
                service = TailorService(db)
                app = await service.tailor_for_listing(listing_id, user_id)
                return {"application_id": app.id if app else None}
        finally:
            await engine.dispose()

    result = asyncio.run(_run())
    application_id = result.get("application_id")
    if application_id:
        # Pass the board_id (= listing.source) so the apply worker routes
        # to the correct per-board applier instead of the generic filler.
        from app.workers.apply_worker import submit_application

        async def _get_board_id():
            from sqlalchemy import select
            from app.models.pg.job_hunter import Application, JobListing
            Session, engine = _make_session()
            try:
                async with Session() as db:
                    app_row = (await db.execute(
                        select(Application).where(Application.id == application_id)
                    )).scalar_one_or_none()
                    if not app_row:
                        return None
                    listing = (await db.execute(
                        select(JobListing).where(JobListing.id == app_row.job_listing_id)
                    )).scalar_one_or_none()
                    return listing.source if listing else None
            finally:
                await engine.dispose()

        board_id = asyncio.run(_get_board_id())
        submit_application.delay(application_id, board_id)
    return result
