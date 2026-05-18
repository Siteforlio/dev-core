import asyncio
import logging
import sys

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
logging.getLogger("uvicorn.access").propagate = True

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
from app.graph.seed import run_seed
from app.graph.knowledge_seed import seed_knowledge_profiles
from app.core.database import AsyncSessionLocal
from app.workers.community_flush import flush_loop

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_seed()
    async with AsyncSessionLocal() as db:
        await seed_knowledge_profiles(db)
    flush_task = asyncio.create_task(flush_loop())
    yield
    flush_task.cancel()
    try:
        await flush_task
    except asyncio.CancelledError:
        pass


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


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
