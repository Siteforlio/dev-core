import asyncio
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
from app.api.v1.job_hunter.ws import router as jh_ws_router
from app.graph.seed import run_seed
from app.workers.community_flush import flush_loop

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_seed()
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
app.include_router(jh_ws_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
