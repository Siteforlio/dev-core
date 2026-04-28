from fastapi import APIRouter, WebSocket
from app.services.cluely.overlay_service import OverlayService

router = APIRouter(prefix="/cluely", tags=["cluely"])
_svc = OverlayService()

@router.websocket("/ws")
async def devcore_overlay_ws(websocket: WebSocket):
    await _svc.handle(websocket)
