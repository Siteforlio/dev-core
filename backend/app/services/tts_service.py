import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator

from app.core.config import settings

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice map: hint keywords → Kokoro voice ID
# Callers pass the interviewer persona string; we pick the closest voice.
# ---------------------------------------------------------------------------
KOKORO_VOICE_MAP: dict[str, str] = {
    "female":         "af_bella",
    "recruiter":      "af_bella",
    "hr":             "af_bella",
    "british_female": "bf_emma",
    "british_male":   "bm_george",
    "male":           "am_michael",
    "senior":         "am_michael",
    "technical":      "am_adam",
    "default":        "am_michael",
}

SAMPLE_RATE = 24_000  # Kokoro's native output sample rate

# ---------------------------------------------------------------------------
# Module-level singleton — loaded once, reused across all requests (§4.2)
# ---------------------------------------------------------------------------
_kokoro = None
_kokoro_lock: asyncio.Lock | None = None


def _lock() -> asyncio.Lock:
    """Lazy-init lock so it is created inside a running event loop."""
    global _kokoro_lock
    if _kokoro_lock is None:
        _kokoro_lock = asyncio.Lock()
    return _kokoro_lock


def _resolve_voice(hint: str | None) -> str:
    if not hint:
        return KOKORO_VOICE_MAP["default"]
    lower = hint.lower()
    for key, voice_id in KOKORO_VOICE_MAP.items():
        if key in lower:
            return voice_id
    # Accept a direct Kokoro voice ID (e.g. "am_adam")
    if hint in KOKORO_VOICE_MAP.values():
        return hint
    return KOKORO_VOICE_MAP["default"]


async def _load_kokoro():
    """Load the Kokoro ONNX model into the singleton. CPU-bound → thread. (§4.5)"""
    global _kokoro
    if _kokoro is not None:
        return _kokoro

    async with _lock():
        if _kokoro is not None:
            return _kokoro

        models_dir = Path(settings.kokoro_models_dir)
        onnx_path = models_dir / "kokoro-v0_19.onnx"
        voices_path = models_dir / "voices.bin"

        if not onnx_path.exists() or not voices_path.exists():
            raise RuntimeError(
                f"Kokoro model files not found in {models_dir}. "
                "Run python backend/scripts/download_kokoro.py first."
            )

        from kokoro_onnx import Kokoro  # imported lazily — not installed in tests

        def _load():
            _log.info("Loading Kokoro TTS model from %s …", models_dir)
            instance = Kokoro(str(onnx_path), str(voices_path))
            _log.info("Kokoro TTS model ready")
            return instance

        _kokoro = await asyncio.to_thread(_load)  # CPU-bound load (§4.5)
        return _kokoro


class TTSService:
    """
    Wraps the Kokoro ONNX model for text-to-speech synthesis.

    Layering (§4.2): this service owns all synthesis logic.
    The WebSocket route handler delegates here and does nothing else.
    """

    async def synthesize_stream(
        self,
        text: str,
        voice_hint: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Async generator — yields raw PCM int16 bytes, one chunk per sentence.

        Kokoro splits text at sentence boundaries and synthesises each one
        independently, so the first sentence is ready before the rest are
        processed. This gives low perceived latency on multi-sentence responses.

        Kokoro inference is CPU-bound, so each sentence runs in a thread (§4.5).
        We use a queue + background thread to overlap synthesis with streaming.
        """
        if not text or not text.strip():
            return

        kokoro = await _load_kokoro()
        voice = _resolve_voice(voice_hint)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | Exception | None] = asyncio.Queue()

        def _run_synthesis():
            try:
                import numpy as np
                for samples, _sr in kokoro.create_stream(
                    text, voice=voice, speed=1.0, lang="en-us"
                ):
                    pcm = (np.clip(samples, -1.0, 1.0) * 32_767).astype(np.int16)
                    asyncio.run_coroutine_threadsafe(queue.put(pcm.tobytes()), loop)
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(queue.put(exc), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

        asyncio.get_event_loop().run_in_executor(None, _run_synthesis)

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                _log.error("Kokoro synthesis error: %s", item)
                raise item
            yield item  # type: ignore[misc]

    @staticmethod
    def sample_rate() -> int:
        return SAMPLE_RATE
