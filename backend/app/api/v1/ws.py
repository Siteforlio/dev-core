from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.avatar_service import AvatarService
from app.services.llm_orchestrator import LLMOrchestrator

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/avatar/{session_id}")
async def avatar_ws(websocket: WebSocket, session_id: str):
    """Relay audio bytes from client to Simli avatar session."""
    await websocket.accept()
    service = AvatarService()
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            await service._send_audio_to_session(session_id, audio_bytes)
    except WebSocketDisconnect:
        pass


@router.websocket("/code/{session_id}")
async def code_ws(websocket: WebSocket, session_id: str):
    """Receive code snapshots, return AI interviewer verbal reactions."""
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
    except WebSocketDisconnect:
        pass
