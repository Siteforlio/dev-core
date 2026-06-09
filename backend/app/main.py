import asyncio
import logging
import subprocess
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
from app.api.v1.cluely.ws import router as cluely_ws_router
from app.api.v1.cluely.sessions import router as cluely_sessions_router
from app.api.v1.progress import router as progress_router
from app.api.v1.sim_sessions import router as sim_sessions_router
from app.graph.seed import run_seed
from app.graph.knowledge_seed import seed_knowledge_profiles
from app.core.database import AsyncSessionLocal
from app.workers.community_flush import flush_loop

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

_celery_proc: subprocess.Popen | None = None
_BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/


def _celery_worker_alive() -> bool:
    """Return True if at least one Celery worker is reachable via Redis."""
    try:
        from app.core.celery_app import celery_app
        reply = celery_app.control.ping(timeout=2)
        return bool(reply)
    except Exception:
        return False


def _purge_celery_queues() -> None:
    """
    Purge all pending tasks from Redis queues directly.
    Called at startup so stale tasks from a previous (possibly unclean) shutdown
    don't replay. Redis queue keys match the queue name exactly (Kombu Redis transport).
    """
    _log = logging.getLogger("uvicorn.error")
    try:
        import redis as _redis_lib
        from app.core.config import settings as _s
        _r = _redis_lib.from_url(_s.celery_broker_url, decode_responses=True)
        for _q in ("celery", "tailor"):
            _purged = _r.delete(_q)
            if _purged:
                _log.info("celery: purged stale queue '%s'", _q)
        _r.close()
    except Exception as _pe:
        _log.warning("celery: startup queue purge failed — %s", _pe)


async def _ensure_celery_worker() -> None:
    """Start a Celery worker subprocess if none is currently running."""
    global _celery_proc
    alive = await asyncio.to_thread(_celery_worker_alive)
    if alive:
        logging.getLogger("uvicorn.error").info("celery: worker already running — skipping auto-start")
        return

    # Purge stale queues before starting a fresh worker so tasks from the
    # previous session (which may have been killed mid-flight) don't replay.
    await asyncio.to_thread(_purge_celery_queues)

    logging.getLogger("uvicorn.error").info("celery: no worker detected — starting worker subprocess")
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.core.celery_app.celery_app",
        "worker",
        "--loglevel=info",
        "--pool=solo",   # prefork uses billiard shared memory which fails on Windows
        "-Q", "tailor,celery",  # tailor queue polled first — resume tasks jump the queue
    ]
    try:
        _celery_proc = subprocess.Popen(cmd, cwd=str(_BACKEND_DIR))
        logging.getLogger("uvicorn.error").info("celery: worker started (pid=%d)", _celery_proc.pid)
    except Exception as exc:
        logging.getLogger("uvicorn.error").error("celery: failed to start worker — %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_seed()
    async with AsyncSessionLocal() as db:
        await seed_knowledge_profiles(db)
    flush_task = asyncio.create_task(flush_loop())
    await _ensure_celery_worker()
    yield
    flush_task.cancel()
    try:
        await flush_task
    except asyncio.CancelledError:
        pass
    # Shut down the worker we spawned (if any)
    if _celery_proc is not None and _celery_proc.poll() is None:
        _log = logging.getLogger("uvicorn.error")
        _log.info("celery: shutting down worker (pid=%d)", _celery_proc.pid)
        try:
            from app.core.celery_app import celery_app
            # 1. Purge all queued tasks from Redis so they don't replay on next start
            await asyncio.to_thread(_purge_celery_queues)
            # 2. Revoke active/reserved tasks then shut the worker down
            insp = celery_app.control.inspect(timeout=2)
            active   = insp.active()   or {}
            reserved = insp.reserved() or {}
            for tasks in list(active.values()) + list(reserved.values()):
                for t in tasks:
                    celery_app.control.revoke(t["id"], terminate=True, signal="SIGKILL")
            celery_app.control.broadcast("shutdown", destination=None)
        except Exception:
            pass
        # Give it 8s to exit gracefully, then hard-kill
        try:
            _celery_proc.wait(timeout=8)
            _log.info("celery: worker exited cleanly")
        except subprocess.TimeoutExpired:
            _log.warning("celery: worker did not exit in time — force killing")
            _celery_proc.kill()
            _celery_proc.wait()
    # Gracefully drain active WebSocket connections before Redis/process shutdown
    from app.core import ws_registry
    await ws_registry.close_all(timeout=10.0)
    # Clean up Redis connection pool on shutdown
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
app.include_router(cluely_ws_router,      prefix="/api/v1")
app.include_router(cluely_sessions_router, prefix="/api/v1")
app.include_router(progress_router, prefix="/api/v1")
app.include_router(sim_sessions_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
