import asyncio
from fastapi import APIRouter, WebSocket
from app.core import ws_registry

router = APIRouter(prefix="/cluely", tags=["cluely"])


@router.websocket("/ws")
async def devcore_overlay_ws(websocket: WebSocket):
    ws_registry.register(asyncio.current_task())
    from app.services.cluely.overlay_service import OverlayService
    await OverlayService().handle(websocket)
