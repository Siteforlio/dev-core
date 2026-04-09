from unittest.mock import AsyncMock, patch
from app.services.avatar_service import AvatarService


async def test_create_session_returns_session_id():
    service = AvatarService()
    with patch.object(service, '_call_simli_api', new=AsyncMock(
        return_value={"session_id": "sim_abc123", "ws_url": "wss://simli.ai/session/sim_abc123"}
    )):
        result = await service.create_streaming_session(persona_description="Professional interviewer")
    assert result["session_id"] == "sim_abc123"
    assert "ws_url" in result


async def test_send_audio_chunk_calls_handler():
    service = AvatarService()
    with patch.object(service, '_send_audio_to_session', new=AsyncMock()) as mock_send:
        await service.send_audio(session_id="sim_abc123", audio_bytes=b"audio_data")
        mock_send.assert_called_once_with("sim_abc123", b"audio_data")
