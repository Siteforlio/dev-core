import io
import struct
import time
import wave
import logging
import threading
from typing import Literal

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
# "tiny" → ~75 MB, ~1-2s on CPU per utterance. Upgrade to "base" (~140 MB)
# for better accuracy if CPU budget allows.
_WHISPER_MODEL_SIZE = "tiny"
_WHISPER_DEVICE     = "cpu"
_WHISPER_COMPUTE    = "int8"   # int8 is fastest on CPU with no quality loss at tiny size

MIN_SAMPLES = 1600    # 100 ms at 16 kHz — drop frames shorter than this
MIC_GAIN    = 4.0     # software boost for quiet mic devices

# Exact-match short hallucinations (kept as a safety net even with VAD)
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

# ---------------------------------------------------------------------------
# Singleton model loader (lazy, thread-safe)
# The model is downloaded on first use (~75 MB for tiny).
# ---------------------------------------------------------------------------
_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                logger.info(
                    "[audio] Loading faster-whisper %s on %s (%s) — first run downloads ~75 MB",
                    _WHISPER_MODEL_SIZE, _WHISPER_DEVICE, _WHISPER_COMPUTE,
                )
                _model = WhisperModel(
                    _WHISPER_MODEL_SIZE,
                    device=_WHISPER_DEVICE,
                    compute_type=_WHISPER_COMPUTE,
                )
                logger.info("[audio] faster-whisper model ready")
    return _model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    # Kept for backwards compat — VAD filter inside faster-whisper handles this now
    return _rms(pcm) < 0.008


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# AudioService
# ---------------------------------------------------------------------------

class AudioService:
    """
    Local transcription using faster-whisper (CPU, int8, tiny model).

    Key differences from Groq:
    - vad_filter=True  → silero VAD pre-screens every chunk, eliminating
                          silence hallucinations completely.
    - no_speech_threshold=0.6 → segments below 60% speech probability are
                                 discarded instead of hallucinated.
    - Runs entirely offline, no API costs, no rate limits.
    """

    def __init__(self):
        # Trigger model load in the background so the first real call is fast
        threading.Thread(target=_get_model, daemon=True).start()

    async def transcribe(self, pcm: bytes, speaker: Literal["interviewer", "user"]) -> dict:
        import asyncio
        t_total = time.perf_counter()

        if len(pcm) < MIN_SAMPLES * 2:
            logger.debug("[audio] DROP short frame %d bytes | %s", len(pcm), speaker)
            return {"speaker": speaker, "text": "", "timings": {}}

        if speaker == "user":
            pcm = _boost(pcm, MIC_GAIN)

        rms = _rms(pcm)
        logger.info("[audio] frame %d bytes | rms=%.4f | %s", len(pcm), rms, speaker)

        # Fast RMS gate — skip obvious silence before even touching the model
        if rms < 0.004:
            return {"speaker": speaker, "text": "", "timings": {}}

        wav_bytes = _pcm_to_wav(pcm)

        try:
            # faster-whisper is synchronous — run in a thread to avoid blocking the event loop
            t_infer = time.perf_counter()
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._run_whisper, wav_bytes)
            infer_ms = round((time.perf_counter() - t_infer) * 1000, 1)
        except Exception as e:
            logger.error("[audio] faster-whisper error: %s", e)
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

    def _run_whisper(self, wav_bytes: bytes) -> str:
        """Blocking call — runs in executor thread."""
        model = _get_model()
        audio_file = io.BytesIO(wav_bytes)

        segments, info = model.transcribe(
            audio_file,
            language="en",
            # silero VAD — filters out non-speech before Whisper sees it.
            # This is the main fix for hallucinations on silence/noise.
            vad_filter=True,
            vad_parameters={
                "threshold": 0.5,            # speech probability gate (0–1)
                "min_speech_duration_ms": 250,
                "max_speech_duration_s": 30,
                "min_silence_duration_ms": 300,
                "speech_pad_ms": 100,
            },
            # Discard any segment where Whisper itself isn't confident it's speech
            no_speech_threshold=0.6,
            # Don't hallucinate words at segment boundaries
            condition_on_previous_text=False,
            # Suppress common Whisper hallucination tokens
            suppress_tokens=[-1],
            beam_size=1,          # greedy — fastest, still accurate for short utterances
            temperature=0.0,      # deterministic, no creative hallucination
        )

        # Collect only segments that passed the VAD + no_speech filter
        parts = []
        for seg in segments:
            t = seg.text.strip()
            if t:
                parts.append(t)

        return " ".join(parts)
