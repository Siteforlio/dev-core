"""
Outcome inference and gap detection.

Three-mode system:
  1. Outcome Inference — on question detection, infer what the interviewer
     expects the candidate to land on. Cached per question hash in Redis.

  2. Gap Detection — compare the user's live spoken response against the
     inferred outcome using all-MiniLM embedding similarity (CPU, ~5ms).
     Returns True when drift is detected (similarity < GAP_THRESHOLD).

  3. Outcome Pill — expose the inferred outcome text so the UI can show it.
     The pill also triggers a full first-person answer on demand (handled
     by the LLM service, not here).

Redis key: cluely:outcome:{session_id}:{question_hash}  TTL=1800 (30 min)
"""
import asyncio
import hashlib
import logging
import threading
from typing import Optional

from app.services.cluely.deepseek_client import deepseek_generate

logger = logging.getLogger(__name__)

GAP_THRESHOLD = 0.42        # cosine similarity below this → fire suggestion
OUTCOME_TTL   = 1800        # 30 min — same question in same session reuses outcome
INFER_SYSTEM  = (
    "You are an interview coaching expert. Given a question asked by an interviewer, "
    "write ONE concise sentence (max 15 words) describing what a strong candidate answer "
    "must demonstrate. Start with a verb: 'Demonstrate', 'Show', 'Explain', 'Quantify'. "
    "No preamble. No punctuation at the end."
)

# --- Singleton embedding model (shared with rag_service) ---
_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _embed(texts: list[str]):
    """Synchronous embedding — must be run in a thread."""
    model = _get_model()
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


def _cosine(a, b) -> float:
    """Dot product of two unit-normalized vectors = cosine similarity."""
    return float(a @ b)


class OutcomeService:
    def __init__(self, redis=None):
        self._r = redis

    def _outcome_key(self, session_id: str, q_hash: str) -> str:
        return f"cluely:outcome:{session_id}:{q_hash}"

    def _q_hash(self, question: str) -> str:
        return hashlib.md5(question.strip().lower().encode()).hexdigest()[:12]

    async def infer_outcome(self, session_id: str, question: str, context: dict) -> str:
        """
        Infer the expected interview outcome for a question.
        Returns cached result if seen before; otherwise calls DeepSeek and caches.
        """
        q_hash = self._q_hash(question)
        key = self._outcome_key(session_id, q_hash)

        # Cache check
        if self._r:
            cached = await self._r.get(key)
            if cached:
                outcome = cached.decode() if isinstance(cached, (bytes, bytearray)) else str(cached)
                logger.debug("[outcome] cache hit | q_hash=%s | outcome=%r", q_hash, outcome)
                return outcome

        job_title = context.get("job_title", "the role")
        company   = context.get("company", "the company")
        jd_snippet = context.get("jd_text", "")[:300]

        prompt = (
            f"Interviewer question: \"{question}\"\n"
            f"Role: {job_title} at {company}.\n"
            f"Job description excerpt: {jd_snippet}\n\n"
            "What must a strong candidate demonstrate in their answer?"
        )

        try:
            outcome = await deepseek_generate(
                prompt,
                system=INFER_SYSTEM,
                temperature=0.3,
                max_tokens=40,
            )
            outcome = outcome.strip().rstrip(".")
        except Exception as e:
            logger.warning("[outcome] inference failed: %s", e)
            outcome = f"Demonstrate relevant experience for {job_title}"

        if self._r and outcome:
            await self._r.setex(key, OUTCOME_TTL, outcome)

        logger.info("[outcome] inferred | q_hash=%s | outcome=%r", q_hash, outcome)
        return outcome

    async def detect_gap(self, outcome: str, user_response: str) -> bool:
        """
        Returns True if the user's response is drifting from the expected outcome.
        Uses all-MiniLM cosine similarity — CPU only, no API call.
        """
        if not outcome or not user_response or len(user_response.split()) < 5:
            return False
        try:
            embeddings = await asyncio.to_thread(_embed, [outcome, user_response])
            similarity = _cosine(embeddings[0], embeddings[1])
            logger.debug("[outcome] gap_check | similarity=%.3f | threshold=%.2f", similarity, GAP_THRESHOLD)
            return similarity < GAP_THRESHOLD
        except Exception as e:
            logger.warning("[outcome] gap detection error: %s", e)
            return False
