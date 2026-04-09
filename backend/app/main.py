from fastapi import FastAPI
from app.core.middleware import setup_middleware
from app.core.exceptions import register_exception_handlers
from app.api.v1.auth import router as auth_router

app = FastAPI(title="Developer Core API", version="1.0.0")
setup_middleware(app)
register_exception_handlers(app)

app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
