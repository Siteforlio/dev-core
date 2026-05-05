import io
import struct
import time
import wave
import logging
from typing import Literal

import numpy as np
from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger(__name__)

MIN_SAMPLES = 1600    # 100 ms at 16 kHz — drop frames shorter than this
SILENCE_RMS = 0.002   # below this → silent, skip API call
MIC_GAIN    = 4.0     # software boost for quiet mic devices (applied to mic stream only)

_HALLUCINATIONS = {
    "", ".", "..", "...", " ", "you", "you.", "thank you", "thank you.",
    "thanks.", "thanks for watching.", "bye.", "bye bye.", "goodbye.",
    "ok.", "okay.", "and", "and.", "um", "um.", "uh", "uh.", "so", "so.",
    "i", "i.", "the", "the.",
}


def parse_audio_frame(data: bytes) -> tuple[Literal["mic", "system"], int, bytes]:
    if len(data) < 3:
        raise ValueError("Frame too short")
    stream_id_byte, seq = struct.unpack_from('!BH', data, 0)
    pcm = data[3:]
    stream: Literal["mic", "system"] = "mic" if stream_id_byte == 0x01 else "system"
    return stream, seq, pcm


def _rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples ** 2))) / 32768.0


def _boost(pcm: bytes, gain: float) -> bytes:
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    arr = np.clip(arr * gain, -32768, 32767).astype(np.int16)
    return arr.tobytes()


def detect_silence(pcm: bytes) -> bool:
    """Return True if the PCM buffer is below the silence threshold."""
    return _rms(pcm) < SILENCE_RMS


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw 16-bit mono PCM in a WAV container (in memory)."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class AudioService:
    def __init__(self):
        api_key = settings.groq_api_key
        if not api_key:
            logger.warning("[audio] GROQ_API_KEY not set — transcription disabled")
            self._client = None
        else:
            self._client = AsyncGroq(api_key=api_key)

    async def transcribe(self, pcm: bytes, speaker: Literal["interviewer", "user"]) -> dict:
        t_total = time.perf_counter()

        if len(pcm) < MIN_SAMPLES * 2:
            logger.debug("[audio] DROP short frame %d bytes | %s", len(pcm), speaker)
            return {"speaker": speaker, "text": "", "timings": {}}

        # Boost mic (user) frames — headset mics are typically quiet
        if speaker == "user":
            pcm = _boost(pcm, MIC_GAIN)

        rms = _rms(pcm)
        logger.info("[audio] frame %d bytes | rms=%.4f | %s", len(pcm), rms, speaker)
        if rms < SILENCE_RMS:
            return {"speaker": speaker, "text": "", "timings": {}}

        if self._client is None:
            return {"speaker": speaker, "text": "", "timings": {}}

        try:
            wav_bytes = _pcm_to_wav(pcm)
            t_infer = time.perf_counter()
            # Retry once on 429 — wait the suggested retry-after (default 3s)
            for attempt in range(2):
                try:
                    result = await self._client.audio.transcriptions.create(
                        file=("audio.wav", wav_bytes, "audio/wav"),
                        model="whisper-large-v3-turbo",
                        language="en",
                        response_format="text",
                    )
                    break
                except Exception as e:
                    if attempt == 0 and "429" in str(e):
                        import asyncio as _aio
                        logger.warning("[audio] 429 rate limit — waiting 4s then retrying")
                        await _aio.sleep(4)
                    else:
                        raise
            infer_ms = round((time.perf_counter() - t_infer) * 1000, 1)
            text = result.strip() if isinstance(result, str) else ""
        except Exception as e:
            logger.error("[audio] Groq transcription error: %s", e)
            return {"speaker": speaker, "text": "", "timings": {}}

        if text.lower() in _HALLUCINATIONS:
            logger.debug("[audio] hallucination filtered: %r", text)
            text = ""

        total_ms = round((time.perf_counter() - t_total) * 1000, 1)
        logger.info("[audio] %s | rms=%.4f | infer=%.0fms | total=%.0fms | %r",
                    speaker, rms, infer_ms, total_ms, text[:80])

        return {"speaker": speaker, "text": text, "timings": {"infer_ms": infer_ms, "total_ms": total_ms}}
