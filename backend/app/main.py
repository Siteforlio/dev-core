import asyncio
import logging
import sys
from pathlib import Path

# On Windows, asyncio defaults to SelectorEventLoop which does NOT support
# create_subprocess_exec. Switch to ProactorEventLoop so the terminal tool works.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Windows does not allow symlinks without Developer Mode enabled.
# Patch HuggingFace Hub to copy files instead of symlinking so Semble's
# model2vec download works without requiring elevated privileges.
if sys.platform == "win32":
    try:
        import shutil, os
        import huggingface_hub.file_download as _hf_fd
        def _hf_copy_instead_of_symlink(src: str, dst: str, new_blob: bool = False) -> None:
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
        _hf_fd._create_symlink = _hf_copy_instead_of_symlink
    except Exception:
        pass

# Ensure uvicorn access log is always visible regardless of reload mode
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").propagate = False
# Debug LLM prompts/responses — attach own handler so uvicorn's INFO-level root doesn't suppress it
_llm_logger = logging.getLogger("app.services.job_hunter.llm")
_llm_logger.setLevel(logging.DEBUG)
if not _llm_logger.handlers:
    _llm_handler = logging.StreamHandler()
    _llm_handler.setLevel(logging.DEBUG)
    _llm_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _llm_logger.addHandler(_llm_handler)
    _llm_logger.propagate = False

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.middleware import setup_middleware
from app.core.exceptions import register_exception_handlers
from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.speech import router as speech_router
from app.api.v1.ws import router as ws_router
from app.api.v1.emotion import router as emotion_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.job_hunter.campaigns import router as jh_campaigns_router
from app.api.v1.job_hunter.applications import router as jh_applications_router
from app.api.v1.job_hunter.overlay import router as jh_overlay_router
from app.api.v1.job_hunter.ws import router as jh_ws_router
from app.api.v1.job_hunter.ext import router as jh_ext_router
from app.api.v1.cluely.ws import router as cluely_ws_router
from app.api.v1.cluely.sessions import router as cluely_sessions_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.progress import router as progress_router
from app.api.v1.sim_sessions import router as sim_sessions_router
from app.api.v1.meeting_debrief import router as meeting_debrief_router
from app.graph.seed import run_seed
from app.graph.knowledge_seed import seed_knowledge_profiles
from app.core.database import AsyncSessionLocal
from app.workers.community_flush import flush_loop

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap SQLite schema (creates tables that don't exist; safe every startup)
    # PostgreSQL path: Alembic handles migrations — skip create_all
    if settings.database_url.startswith("sqlite+aiosqlite"):
        # MAINTENANCE: Add new model modules here when new pg model files are created
        # (each module must be imported so SQLAlchemy registers its tables with Base.metadata)
        import app.models.pg.user          # noqa: F401
        import app.models.pg.session       # noqa: F401
        import app.models.pg.job_hunter    # noqa: F401
        import app.models.pg.knowledge     # noqa: F401
        import app.models.pg.meeting_debrief  # noqa: F401
        import app.models.pg.simulation    # noqa: F401
        import app.models.pg.progress      # noqa: F401
        import app.models.pg.community     # noqa: F401
        import app.models.pg.cluely_session  # noqa: F401
        import app.models.pg.graph          # noqa: F401
        import app.models.pg.user_settings  # noqa: F401
        from app.models.pg.base import Base
        from app.core.database import engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await run_seed()
        async with AsyncSessionLocal() as db:
            await seed_knowledge_profiles(db)
    flush_task = asyncio.create_task(flush_loop())
    from app.core.task_runner import get_runner
    from app.workers.scraper_worker import scrape_all_active_campaigns
    from app.workers.email_worker import poll_all_campaigns
    runner = get_runner()
    runner.schedule_periodic(scrape_all_active_campaigns, interval_seconds=21600)  # 6h
    runner.schedule_periodic(poll_all_campaigns, interval_seconds=60)               # 1min
    yield
    flush_task.cancel()
    try:
        await flush_task
    except asyncio.CancelledError:
        pass
    await runner.shutdown()
    # Gracefully drain active WebSocket connections before shutdown
    from app.core import ws_registry
    await ws_registry.close_all(timeout=10.0)
    # Clean up cache on shutdown
    from app.core.cache import close_redis
    await close_redis()


app = FastAPI(title="Developer Core API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

setup_middleware(app)
register_exception_handlers(app)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(speech_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
app.include_router(emotion_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(jh_campaigns_router, prefix="/api/v1")
app.include_router(jh_applications_router, prefix="/api/v1")
app.include_router(jh_overlay_router, prefix="/api/v1")
app.include_router(jh_ws_router, prefix="/api/v1")
app.include_router(jh_ext_router, prefix="/api/v1")
app.include_router(cluely_ws_router,      prefix="/api/v1")
app.include_router(cluely_sessions_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(progress_router, prefix="/api/v1")
app.include_router(sim_sessions_router, prefix="/api/v1")
app.include_router(meeting_debrief_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
