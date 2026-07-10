import logging
from app.services.tts_service import TTSService

_log = logging.getLogger(__name__)


class SpeechService:
    """
    Public speech façade used by HTTP route handlers.

    TTS is delegated to TTSService (Kokoro ONNX).
    STT uses Deepgram for accurate multilingual transcription.
    """

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    async def synthesize(self, text: str, language: str = "en") -> bytes:  # noqa: ARG002
        """Return the full audio as a single MP3-compatible byte blob (WAV/PCM)."""
        svc = TTSService()
        chunks: list[bytes] = []
        async for chunk in svc.synthesize_stream(text):
            chunks.append(chunk)
        return b"".join(chunks)

    def synthesize_stream(self, text: str, voice_hint: str | None = None):
        """Async generator — yields raw PCM int16 chunks. Used by the WS endpoint."""
        return TTSService().synthesize_stream(text, voice_hint=voice_hint)

    # ------------------------------------------------------------------
    # STT
    # ------------------------------------------------------------------

    async def transcribe(self, audio_bytes: bytes, language_hint: str = "en") -> str:
        from deepgram import AsyncDeepgramClient
        from app.core.config import settings as _settings

        client = AsyncDeepgramClient(api_key=_settings.deepgram_api_key)
        response = await client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-2",
            language=language_hint,
            smart_format=True,
            punctuate=True,
        )
        return (response.results.channels[0].alternatives[0].transcript or "").strip()

    async def transcribe_with_language(self, audio_bytes: bytes) -> dict:
        from deepgram import AsyncDeepgramClient
        from app.core.config import settings as _settings

        client = AsyncDeepgramClient(api_key=_settings.deepgram_api_key)
        response = await client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-2",
            smart_format=True,
            punctuate=True,
            detect_language=True,
        )
        channel = response.results.channels[0]
        text = (channel.alternatives[0].transcript or "").strip()
        lang = getattr(channel, "detected_language", "en") or "en"
        return {"transcript": text, "detected_language": lang}
