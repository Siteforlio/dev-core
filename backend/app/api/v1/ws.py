import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_token
from app.core.exceptions import InvalidCredentialsError
from app.core import ws_registry
from app.services.avatar_service import AvatarService
from app.services.llm_orchestrator import LLMOrchestrator

router = APIRouter(prefix="/ws", tags=["websocket"])


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> str | None:
    """
    Validate Bearer token before accepting the WebSocket connection.
    Returns user_id on success, closes the connection with 4001 on failure.
    """
    if not token:
        await websocket.close(code=4001)
        return None
    try:
        user_id = decode_token(token)
        return user_id
    except InvalidCredentialsError:
        await websocket.close(code=4001)
        return None


@router.websocket("/avatar/{session_id}")
async def avatar_ws(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    """Relay audio bytes from client to Simli avatar session."""
    user_id = await _authenticate_ws(websocket, token)
    if user_id is None:
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    service = AvatarService()
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            await service._send_audio_to_session(session_id, audio_bytes)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass


@router.websocket("/code/{session_id}")
async def code_ws(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    """Receive code snapshots, return AI interviewer verbal reactions."""
    user_id = await _authenticate_ws(websocket, token)
    if user_id is None:
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    orchestrator = LLMOrchestrator()
    try:
        while True:
            data = await websocket.receive_json()
            comment = await orchestrator.react_to_code(
                code_snapshot=data["code"],
                question=data["question"],
                company=data["company"],
            )
            await websocket.send_json({"reaction": comment})
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
