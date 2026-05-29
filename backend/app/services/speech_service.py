import io
import openai
from app.core.config import settings

# OpenAI TTS voices — onyx is deep/authoritative (interviewer), nova is warmer
TTS_VOICE = "onyx"


class SpeechService:
    def __init__(self):
        self._openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def synthesize(self, text: str, language: str = "en") -> bytes:  # noqa: ARG002
        """Synthesize speech using OpenAI TTS (tts-1). Language is inferred from text."""
        response = await self._openai_client.audio.speech.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=text,
            response_format="mp3",
        )
        return response.content

    async def synthesize_stream(self, text: str):
        """Yield MP3 chunks as bytes using OpenAI streaming TTS."""
        async with self._openai_client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=text,
            response_format="mp3",
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk

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
