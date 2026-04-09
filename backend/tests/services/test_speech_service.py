from unittest.mock import AsyncMock, MagicMock, patch
from app.services.speech_service import SpeechService


async def test_synthesize_returns_audio_bytes():
    service = SpeechService()
    fake_audio = b"RIFF....fake_wav_data"
    with patch.object(service, '_edge_tts_synthesize', new=AsyncMock(return_value=fake_audio)):
        result = await service.synthesize(text="Tell me about yourself.", language="en")
    assert isinstance(result, bytes)
    assert len(result) > 0


async def test_synthesize_selects_voice_by_language():
    service = SpeechService()
    with patch.object(service, '_edge_tts_synthesize', new=AsyncMock(return_value=b"audio")) as mock_tts:
        await service.synthesize(text="Hola", language="es")
        call_args = mock_tts.call_args
        assert "es" in call_args[1].get("voice", "") or call_args[0][1].startswith("es")


async def test_transcribe_returns_text():
    service = SpeechService()
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="I am a software engineer.")
    )
    service._openai_client = mock_client
    result = await service.transcribe(audio_bytes=b"fake_audio", language_hint="en")
    assert result == "I am a software engineer."
