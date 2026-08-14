import asyncio
from fastapi import APIRouter, WebSocket
from app.core import ws_registry

router = APIRouter(prefix="/cluely", tags=["cluely"])

_svc: 'OverlayService | None' = None


def _get_svc() -> 'OverlayService':
    global _svc
    if _svc is None:
        from app.services.cluely.overlay_service import OverlayService
        _svc = OverlayService()
    return _svc


@router.websocket("/ws")
async def devcore_overlay_ws(websocket: WebSocket):
    ws_registry.register(asyncio.current_task())
    await _get_svc().handle(websocket)
