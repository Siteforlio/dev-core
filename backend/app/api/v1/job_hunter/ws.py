import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.cache import get_redis
from app.core.security import decode_token

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
                await websocket.send_text(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for campaign %s", campaign_id)
    finally:
        await pubsub.unsubscribe(f"campaign:{campaign_id}:activity")
