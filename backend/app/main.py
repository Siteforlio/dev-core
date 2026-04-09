from fastapi import FastAPI
from app.core.middleware import setup_middleware

app = FastAPI(title="Developer Core API", version="1.0.0")
setup_middleware(app)

@app.get("/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}
