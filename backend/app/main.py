from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.middleware import setup_middleware
from app.core.exceptions import register_exception_handlers
from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.sessions import router as sessions_router
from app.graph.seed import run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_seed()
    yield


app = FastAPI(title="Developer Core API", version="1.0.0", lifespan=lifespan)
setup_middleware(app)
register_exception_handlers(app)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
