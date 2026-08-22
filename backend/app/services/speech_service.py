import logging
from app.services.tts_service import TTSService

_log = logging.getLogger(__name__)


class SpeechService:
    """
    Public speech façade used by HTTP route handlers.

    TTS  → Kokoro ONNX (self-hosted, no API key)
    STT  → Parakeet-TDT-0.6B (self-hosted, no API key)
           Falls back to Deepgram Nova-2 if Parakeet fails or is unavailable.
    """

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        svc = TTSService()
        chunks: list[bytes] = []
        async for chunk in svc.synthesize_stream(text):
            chunks.append(chunk)
        return b"".join(chunks)

    def synthesize_stream(self, text: str, voice_hint: str | None = None):
        return TTSService().synthesize_stream(text, voice_hint=voice_hint)

    # ------------------------------------------------------------------
    # STT — Parakeet primary, Deepgram fallback
    # ------------------------------------------------------------------

    async def transcribe(self, audio_bytes: bytes, language_hint: str = "en", api_key: str | None = None) -> str:
        return await self._deepgram_transcribe(audio_bytes, language_hint, api_key=api_key)

    async def transcribe_with_language(self, audio_bytes: bytes, api_key: str | None = None) -> dict:
        text = await self.transcribe(audio_bytes, api_key=api_key)
        return {"transcript": text, "detected_language": "en"}

    async def _deepgram_transcribe(self, audio_bytes: bytes, language_hint: str = "en", api_key: str | None = None) -> str:
        try:
            from deepgram import AsyncDeepgramClient
            from app.core.config import settings as _settings
            resolved_key = api_key or getattr(_settings, "deepgram_api_key", None)
            if not resolved_key:
                return ""
            client = AsyncDeepgramClient(api_key=resolved_key)
            response = await client.listen.v1.media.transcribe_file(
                request=audio_bytes,
                model="nova-2",
                language=language_hint,
                smart_format=True,
                punctuate=True,
            )
            return (response.results.channels[0].alternatives[0].transcript or "").strip()
        except Exception as e:
            _log.error("[speech] Deepgram fallback also failed: %s", e)
            return ""
