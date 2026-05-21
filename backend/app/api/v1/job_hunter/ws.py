import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.cache import get_redis
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
    except Exception:
        await websocket.close(code=1008)  # Policy Violation
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"campaign:{campaign_id}:activity")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                try:
                    await websocket.send_text(data)
                except Exception:
                    break  # client disconnected — exit cleanly
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        pass  # shutdown or network error — exit silently
    finally:
        try:
            await pubsub.unsubscribe(f"campaign:{campaign_id}:activity")
            await pubsub.aclose()
        except Exception:
            pass
