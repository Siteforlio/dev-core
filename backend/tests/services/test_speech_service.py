from unittest.mock import AsyncMock, MagicMock
from app.services.speech_service import SpeechService


async def test_synthesize_returns_audio_bytes():
    service = SpeechService()
    fake_audio = b"ID3\x00\x00fake_mp3_data"
    mock_client = MagicMock()
    mock_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=fake_audio)
    )
    service._openai_client = mock_client
    result = await service.synthesize(text="Tell me about yourself.", language="en")
    assert isinstance(result, bytes)
    assert len(result) > 0


async def test_synthesize_calls_tts1_model():
    service = SpeechService()
    mock_client = MagicMock()
    mock_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"audio")
    )
    service._openai_client = mock_client
    await service.synthesize(text="Hello", language="es")
    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["model"] == "tts-1"
    assert call_kwargs["voice"] == "onyx"


async def test_transcribe_returns_text():
    service = SpeechService()
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="I am a software engineer.")
    )
    service._openai_client = mock_client
    result = await service.transcribe(audio_bytes=b"fake_audio", language_hint="en")
    assert result == "I am a software engineer."
