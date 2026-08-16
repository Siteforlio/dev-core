import uuid
import structlog
import structlog.contextvars
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = structlog.get_logger()

def setup_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # must be False when allow_origins="*"
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def private_network_access_middleware(request: Request, call_next):
        """
        Chrome Private Network Access (PNA) blocks https pages → http://localhost
        unless the server explicitly allows it in the preflight response.
        """
        response = await call_next(request)
        if request.headers.get("access-control-request-private-network") == "true":
            response.headers["access-control-allow-private-network"] = "true"
        return response

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        from app.core.exceptions import DevCoreException
        structlog.contextvars.clear_contextvars()
        correlation_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        except DevCoreException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"data": None, "error": {"code": exc.code, "message": exc.message}},
                headers={"X-Correlation-ID": correlation_id},
            )
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"data": None, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
                headers={"X-Correlation-ID": correlation_id},
            )
        response.headers["X-Correlation-ID"] = correlation_id
        return response
