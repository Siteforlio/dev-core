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
MIC_GAIN    = 4.0     # software boost for quiet mic devices

# Exact-match short hallucinations — safety net in case Groq returns junk
_HALLUCINATIONS = {
    "", ".", "..", "...", " ", "you", "you.", "thank you", "thank you.",
    "thanks.", "thanks for watching.", "bye.", "bye bye.", "goodbye.",
    "ok.", "okay.", "and", "and.", "um", "um.", "uh", "uh.", "so", "so.",
    "i", "i.", "the", "the.", "mm-hmm.", "mm-hmm", "hmm.", "hmm",
}

_HALLUCINATION_FRAGMENTS = [
    "please don't forget to subscribe",
    "don't forget to subscribe",
    "subscribe if you like",
    "thanks for watching",
    "like and subscribe",
    "see you next time",
    "have a great day",
    "www.",
    "http",
    "subtitles by",
    "transcribed by",
    "amara.org",
]


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
    return _rms(pcm) < 0.008


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class AudioService:
    """
    Transcription via Groq Whisper API (whisper-large-v3-turbo).

    Silence hallucinations are prevented upstream — Electron's VAD gate only
    sends speech segments, so Groq never receives silent audio.

    Latency: ~200-300ms round-trip vs ~800ms-1.5s for local CPU inference.
    """

    def __init__(self):
        self._client = AsyncGroq(api_key=settings.groq_api_key)

    async def transcribe(self, pcm: bytes, speaker: Literal["interviewer", "user"]) -> dict:
        t_total = time.perf_counter()

        if len(pcm) < MIN_SAMPLES * 2:
            logger.debug("[audio] DROP short frame %d bytes | %s", len(pcm), speaker)
            return {"speaker": speaker, "text": "", "timings": {}}

        if speaker == "user":
            pcm = _boost(pcm, MIC_GAIN)

        rms = _rms(pcm)
        logger.info("[audio] frame %d bytes | rms=%.4f | %s", len(pcm), rms, speaker)

        # Fast RMS gate — drop anything still silent after the Electron VAD
        if rms < 0.004:
            return {"speaker": speaker, "text": "", "timings": {}}

        wav_bytes = _pcm_to_wav(pcm)

        try:
            t_infer = time.perf_counter()
            result = await self._client.audio.transcriptions.create(
                file=("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
                model="whisper-large-v3-turbo",
                language="en",
                response_format="text",
            )
            infer_ms = round((time.perf_counter() - t_infer) * 1000, 1)
            text = result.strip() if isinstance(result, str) else (result.text or "").strip()
        except Exception as e:
            logger.error("[audio] Groq transcription error: %s", e)
            return {"speaker": speaker, "text": "", "timings": {}}

        text_lower = text.lower()
        if text_lower in _HALLUCINATIONS:
            logger.debug("[audio] hallucination filtered (exact): %r", text)
            text = ""
        elif any(frag in text_lower for frag in _HALLUCINATION_FRAGMENTS):
            logger.debug("[audio] hallucination filtered (fragment): %r", text)
            text = ""

        total_ms = round((time.perf_counter() - t_total) * 1000, 1)
        logger.info("[audio] %s | rms=%.4f | infer=%.0fms | total=%.0fms | %r",
                    speaker, rms, infer_ms, total_ms, text[:80])

        return {"speaker": speaker, "text": text, "timings": {"infer_ms": infer_ms, "total_ms": total_ms}}
