"""
Self-hosted STT using NVIDIA Parakeet-TDT-0.6B via HuggingFace Transformers.

Model: nvidia/parakeet-tdt-0.6b
- TDT (Token-and-Duration Transducer) architecture
- Best accuracy-to-speed ratio on CPU
- Strong accent handling due to diverse training data
- ~0.1-0.15x RTF on modern Intel CPU (real-time capable)
- ~2.2GB download on first run, cached in HuggingFace cache

No API key required — fully self-hosted.
"""

import asyncio
import io
import logging
import wave
import numpy as np

_log = logging.getLogger(__name__)

# Module-level singleton — loaded once on first transcription call.
# Loading takes ~5-10s; subsequent calls are fast.
_pipeline = None
_pipeline_lock = asyncio.Lock()

MODEL_ID = "nvidia/parakeet-tdt-0.6b-v2"


def _load_pipeline():
    """Load the Parakeet pipeline synchronously (called in thread pool)."""
    from transformers import pipeline as hf_pipeline

    _log.info("[parakeet] Loading %s — this may take a moment on first run…", MODEL_ID)
    pipe = hf_pipeline(
        task="automatic-speech-recognition",
        model=MODEL_ID,
        device="cpu",
        chunk_length_s=30,       # process in 30s chunks for long audio
        stride_length_s=5,       # 5s overlap between chunks for accuracy
        return_timestamps=False,
        trust_remote_code=True,  # required: Parakeet uses NeMo format config
    )
    _log.info("[parakeet] Model loaded and ready.")
    return pipe


async def _get_pipeline():
    """Return the singleton pipeline, loading it on first call."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    async with _pipeline_lock:
        # Double-check after acquiring lock
        if _pipeline is None:
            loop = asyncio.get_event_loop()
            _pipeline = await loop.run_in_executor(None, _load_pipeline)

    return _pipeline


def _wav_bytes_to_float32(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """
    Convert WAV bytes to float32 numpy array.
    Handles mono/stereo, any sample rate (resamples to 16kHz if needed).
    Returns (audio_float32, sample_rate).
    """
    with io.BytesIO(audio_bytes) as f:
        try:
            with wave.open(f) as wav:
                n_channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                frame_rate = wav.getframerate()
                frames = wav.readframes(wav.getnframes())
        except Exception:
            # Not a WAV file — treat as raw PCM s16le at 16kHz
            frames = audio_bytes
            n_channels = 1
            sample_width = 2
            frame_rate = 16000

    # Convert bytes to int16 numpy array
    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    # Downmix stereo → mono
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    # Resample to 16kHz if needed (Parakeet native rate)
    if frame_rate != 16000:
        try:
            import scipy.signal as ss
            audio = ss.resample_poly(audio, 16000, frame_rate).astype(np.float32)
        except ImportError:
            # scipy not available — crude resample via numpy
            target_len = int(len(audio) * 16000 / frame_rate)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, target_len),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)
        frame_rate = 16000

    return audio, frame_rate


async def transcribe(audio_bytes: bytes, language_hint: str = "en") -> str:
    """
    Transcribe audio bytes using Parakeet-TDT-0.6B.

    Args:
        audio_bytes: WAV or raw PCM bytes from the microphone.
        language_hint: Unused (Parakeet is English-only). Kept for API compat.

    Returns:
        Transcribed text string, stripped of leading/trailing whitespace.
    """
    if not audio_bytes:
        return ""

    pipe = await _get_pipeline()

    try:
        audio, sample_rate = _wav_bytes_to_float32(audio_bytes)
    except Exception as e:
        _log.warning("[parakeet] Audio decode failed: %s", e)
        return ""

    if len(audio) < 1600:  # less than 0.1s of audio — skip
        return ""

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: pipe({"raw": audio, "sampling_rate": sample_rate}),
        )
        text = (result.get("text") or "").strip()
        _log.debug("[parakeet] transcript=%r  samples=%d", text[:80], len(audio))
        return text
    except Exception as e:
        _log.error("[parakeet] Transcription failed: %s", e)
        return ""


async def warmup():
    """
    Pre-load the model at server startup so the first real transcription
    isn't delayed. Call this from the FastAPI lifespan handler.
    """
    try:
        await _get_pipeline()
    except Exception as e:
        _log.warning("[parakeet] Warmup failed (Deepgram fallback will be used): %s", e)
