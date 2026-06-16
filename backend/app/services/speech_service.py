import io
import openai
import edge_tts
from app.core.config import settings

# edge-tts voice — en-US-GuyNeural sounds authoritative (interviewer)
EDGE_TTS_VOICE = "en-US-GuyNeural"


class SpeechService:
    def __init__(self):
        self._openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def synthesize(self, text: str, language: str = "en") -> bytes:  # noqa: ARG002
        """Synthesize speech using edge-tts (free, no quota)."""
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    async def synthesize_stream(self, text: str):
        """Yield audio chunks using edge-tts (free, no quota)."""
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk["data"]:
                yield chunk["data"]

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
