import io
import edge_tts
import openai
from app.core.config import settings

LANGUAGE_VOICE_MAP = {
    "en": "en-US-JennyNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "pt": "pt-BR-AntonioNeural",
    "sw": "sw-KE-RafikiNeural",
    "de": "de-DE-ConradNeural",
    "zh": "zh-CN-YunxiNeural",
    "ja": "ja-JP-KeitaNeural",
    "ko": "ko-KR-InJoonNeural",
    "ar": "ar-SA-HamedNeural",
    "hi": "hi-IN-MadhurNeural",
    "ru": "ru-RU-DmitryNeural",
    "it": "it-IT-DiegoNeural",
    "nl": "nl-NL-MaartenNeural",
    "pl": "pl-PL-MarekNeural",
    "tr": "tr-TR-AhmetNeural",
    "vi": "vi-VN-NamMinhNeural",
    "th": "th-TH-NiwatNeural",
    "id": "id-ID-ArdiNeural",
    "uk": "uk-UA-OstapNeural",
}
DEFAULT_VOICE = "en-US-JennyNeural"


class SpeechService:
    def __init__(self):
        self._openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def _edge_tts_synthesize(self, text: str, voice: str) -> bytes:
        buf = io.BytesIO()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        voice = LANGUAGE_VOICE_MAP.get(language, DEFAULT_VOICE)
        return await self._edge_tts_synthesize(text=text, voice=voice)

    async def transcribe(self, audio_bytes: bytes, language_hint: str = "en") -> str:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"
        transcript = await self._openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language_hint,
        )
        return transcript.text

    async def transcribe_with_language(self, audio_bytes: bytes) -> dict:
        """Transcribe and return both text and Whisper-detected language."""
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"
        transcript = await self._openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
        )
        return {
            "transcript": transcript.text,
            "detected_language": getattr(transcript, "language", "en"),
        }
