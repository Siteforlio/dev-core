import asyncio
import struct
import math
import threading
from typing import Literal
import whisper
import numpy as np
import logging

logger = logging.getLogger(__name__)

_whisper_model = None
_whisper_lock = threading.Lock()

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        with _whisper_lock:
            if _whisper_model is None:
                _whisper_model = whisper.load_model("tiny")
    return _whisper_model


def parse_audio_frame(data: bytes) -> tuple[Literal["mic", "system"], int, bytes]:
    """Parse 3-byte header: uint8 stream_id + uint16 big-endian seq. Returns (stream, seq, pcm)."""
    if len(data) < 3:
        raise ValueError("Frame too short")
    stream_id_byte, seq = struct.unpack_from('!BH', data, 0)
    pcm = data[3:]
    stream: Literal["mic", "system"] = "mic" if stream_id_byte == 0x01 else "system"
    return stream, seq, pcm


def detect_silence(pcm: bytes, threshold: float = 0.01, sample_rate: int = 16000) -> bool:
    """True if the RMS of the PCM buffer is below threshold (normalized -1..1)."""
    samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
    if not samples:
        return True
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
    return rms < threshold


class AudioService:
    async def transcribe(self, pcm: bytes, speaker: Literal["interviewer", "user"]) -> dict:
        """Transcribe raw PCM16 mono 16kHz. Returns {speaker, text}. CPU-bound → thread."""
        def _run():  # must be sync — asyncio.to_thread runs in a thread pool, not event loop
            model = _get_model()
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            result = model.transcribe(samples, language=None)
            return {"speaker": speaker, "text": result["text"].strip()}
        return await asyncio.to_thread(_run)
