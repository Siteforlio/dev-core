import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.event_bus import subscribe, unsubscribe
from app.core.security import decode_token
from app.core import ws_registry

router = APIRouter(tags=["job-hunter-ws"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/campaign/{campaign_id}/activity")
async def campaign_activity_feed(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(...),
):
    # Authenticate before accepting
    try:
        decode_token(token)
    except Exception as exc:
        logger.warning("WS auth rejected for campaign %s: %s — token_tail=...%s", campaign_id, exc, token[-12:])
        await websocket.close(code=1008)  # Policy Violation
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    q = subscribe(f"campaign:{campaign_id}:activity")
    try:
        while True:
            try:
                message = await asyncio.wait_for(q.get(), timeout=30.0)
                try:
                    await websocket.send_text(message)
                except Exception:
                    break  # client disconnected — exit cleanly
            except asyncio.TimeoutError:
                pass  # no messages — loop again (keepalive via silence)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        pass  # shutdown or network error — exit silently
    finally:
        unsubscribe(f"campaign:{campaign_id}:activity", q)
