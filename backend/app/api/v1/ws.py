import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_token
from app.core.exceptions import InvalidCredentialsError
from app.core import ws_registry
from app.core.database import AsyncSessionLocal
from app.core.config import get_api_key
from app.services.avatar_service import AvatarService
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.tts_service import TTSService, SAMPLE_RATE

_log = logging.getLogger(__name__)

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

    async with AsyncSessionLocal() as _db:
        simli_key = await get_api_key(user_id, "simli_api_key", _db)

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    service = AvatarService()
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            await service._send_audio_to_session(session_id, audio_bytes)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass


@router.websocket("/tts/{session_id}")
async def tts_ws(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    """
    Stream Kokoro TTS audio to the interview client.

    Protocol (thin handler — all synthesis in TTSService, §4.2):
      Client → Server JSON:  { "type": "speak", "text": "...", "voice": "am_michael" }
      Client → Server JSON:  { "type": "interrupt" }
      Server → Client JSON:  { "type": "meta", "sample_rate": 24000, "channels": 1 }
      Server → Client bytes: raw PCM int16 chunks (one per sentence)
      Server → Client JSON:  { "type": "done" }
      Server → Client JSON:  { "type": "interrupted" }
    """
    user_id = await _authenticate_ws(websocket, token)
    if user_id is None:
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    await websocket.send_json({"type": "meta", "sample_rate": SAMPLE_RATE, "channels": 1})

    service = TTSService()
    speak_task: asyncio.Task | None = None

    async def _do_speak(text: str, voice: str | None) -> None:
        try:
            async for chunk in service.synthesize_stream(text, voice_hint=voice):
                await websocket.send_bytes(chunk)
            await websocket.send_json({"type": "done"})
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _log.error("[tts_ws] synthesis error for session %s: %s", session_id, exc)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "speak":
                # Cancel any in-flight synthesis before starting a new one
                if speak_task and not speak_task.done():
                    speak_task.cancel()
                    try:
                        await speak_task
                    except asyncio.CancelledError:
                        pass
                speak_task = asyncio.create_task(
                    _do_speak(data.get("text", ""), data.get("voice"))
                )

            elif msg_type == "interrupt":
                if speak_task and not speak_task.done():
                    speak_task.cancel()
                    try:
                        await speak_task
                    except asyncio.CancelledError:
                        pass
                await websocket.send_json({"type": "interrupted"})

    except (WebSocketDisconnect, asyncio.CancelledError):
        if speak_task and not speak_task.done():
            speak_task.cancel()


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

    async with AsyncSessionLocal() as _db:
        deepseek_key = await get_api_key(user_id, "deepseek_api_key", _db)

    ws_registry.register(asyncio.current_task())
    await websocket.accept()
    orchestrator = LLMOrchestrator(api_key=deepseek_key)
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
