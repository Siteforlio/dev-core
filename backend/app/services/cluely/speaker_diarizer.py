"""
speaker_diarizer.py — Per-session speaker identity tracking.

Strategy
--------
The overlay captures two separate audio streams:
  • mic (stream_id=0x01)   → always the local user
  • system (stream_id=0x02) → playback from speakers (interviewer in a call,
                               but may also contain echo of the user's own voice)

This service uses voice embeddings to verify system-audio frames:
  1. Enroll user voice from the first N mic frames (clean samples, no noise).
  2. For every system-audio frame, compute cosine similarity against the
     enrolled user embedding.
  3. If similarity ≥ threshold → label "user" (echo / bleed-through).
     Otherwise → label "interviewer".
  4. Falls back to stream-based labeling ("system" → "interviewer") if
     resemblyzer is not installed or enrollment has not gathered enough data.

Dependencies
------------
  resemblyzer (optional but recommended) — pip install resemblyzer
  numpy (always available via sentence-transformers / scikit-learn)
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

_np = None


def _get_np():
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np

# Number of mic frames required before we trust the enrolled embedding.
_MIN_ENROLL_FRAMES = 5
# Cosine similarity threshold: ≥ this value → frame is the enrolled user.
_SIMILARITY_THRESHOLD = 0.75


def _cosine_similarity(a, b) -> float:
    np = _get_np()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / (denom + 1e-8))


class SpeakerDiarizer:
    """
    Lightweight speaker diarization for interview sessions.

    Thread-safety: enroll_user and classify_system_audio are called from
    a single asyncio event loop (via asyncio.to_thread), so no locks needed.
    """

    def __init__(self) -> None:
        self._encoder = None
        self._available = False
        self._enroll_count = 0
        self._running_sum = None
        self._user_embedding = None

        try:
            from resemblyzer import VoiceEncoder  # type: ignore
            self._encoder = VoiceEncoder(device="cpu", verbose=False)
            self._available = True
            logger.info("[diarizer] resemblyzer voice encoder ready")
        except Exception as exc:
            logger.info(
                "[diarizer] resemblyzer not available (%s) — falling back to "
                "stream-based labeling. Install with: pip install resemblyzer",
                exc,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def ready(self) -> bool:
        """True once we have enough enrollment data to make predictions."""
        return self._available and self._enroll_count >= _MIN_ENROLL_FRAMES

    def enroll_user(self, pcm: bytes) -> None:
        """
        Feed a mic-stream PCM frame to build the user's voice embedding.
        Accumulates a running mean so later samples refine the profile.
        No-op if resemblyzer is unavailable or frame is too short.
        """
        if not self._available:
            return
        embedding = self._embed(pcm)
        if embedding is None:
            return

        if self._running_sum is None:
            self._running_sum = embedding.copy()
        else:
            self._running_sum += embedding

        self._enroll_count += 1
        self._user_embedding = self._running_sum / self._enroll_count

        if self._enroll_count == _MIN_ENROLL_FRAMES:
            logger.info("[diarizer] user voice enrolled after %d frames", self._enroll_count)

    def classify_system_audio(self, pcm: bytes) -> Literal["user", "interviewer"]:
        """
        Classify a system-audio PCM frame as either the enrolled user
        (echo / bleed) or the interviewer.

        Returns "interviewer" when:
          • resemblyzer is not installed, or
          • not enough enrollment data yet, or
          • embedding similarity is below threshold.
        """
        if not self.ready or self._user_embedding is None:
            return "interviewer"

        embedding = self._embed(pcm)
        if embedding is None:
            return "interviewer"

        sim = _cosine_similarity(self._user_embedding, embedding)
        speaker: Literal["user", "interviewer"] = (
            "user" if sim >= _SIMILARITY_THRESHOLD else "interviewer"
        )
        logger.debug("[diarizer] system sim=%.3f → %s", sim, speaker)
        return speaker

    def reset(self) -> None:
        """Clear enrollment data. Call at the start of each new session."""
        self._enroll_count = 0
        self._running_sum = None
        self._user_embedding = None
        logger.debug("[diarizer] enrollment reset for new session")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed(self, pcm: bytes):
        """Convert raw 16-bit mono 16 kHz PCM to a d-vector embedding."""
        if self._encoder is None:
            return None
        try:
            np = _get_np()
            # resemblyzer expects float32 waveform normalised to [-1, 1]
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            if samples.size < 1600:  # < 100 ms at 16 kHz — too short
                return None
            return self._encoder.embed_utterance(samples)
        except Exception as exc:
            logger.debug("[diarizer] embed failed: %s", exc)
            return None
