# backend/app/services/job_hunter/bert_scorer.py
"""
Two-stage job scoring pipeline:

  Stage 1 — BERT pre-filter (local, zero cost)
    Encodes the candidate profile and all scraped jobs as embeddings.
    Jobs below BERT_PASS_THRESHOLD are dropped immediately — they never
    touch the LLM. CPU-bound encoding runs in asyncio.to_thread().

  Stage 2 — LLM final classification (DeepSeek, per-token cost)
    Only jobs that passed BERT are sent to the LLM.
    Jobs are batched (BERT_BATCH_LLM_SIZE per API call) to minimise
    the number of requests.

Config (all via environment variables):
  BERT_PASS_THRESHOLD     float  default 0.32  — cosine similarity cutoff
  BERT_LLM_BATCH_SIZE     int    default 15    — jobs per LLM API call
  BERT_MODEL_NAME         str    default all-MiniLM-L6-v2

Architecture rules followed:
  - All business logic in service layer (Section 4.2)
  - CPU-bound ops wrapped in asyncio.to_thread() (Section 4.5)
  - All config via environment variables (Section 4.6)
  - snake_case files/functions, UPPER_SNAKE_CASE constants (Section 4.3)
"""
from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Constants (overridable via env) ───────────────────────────────────────────

BERT_PASS_THRESHOLD = float(os.environ.get("BERT_PASS_THRESHOLD", "0.32"))
BERT_LLM_BATCH_SIZE = int(os.environ.get("BERT_LLM_BATCH_SIZE", "15"))
BERT_MODEL_NAME     = os.environ.get("BERT_MODEL_NAME", "all-MiniLM-L6-v2")


# ── Model singleton — loaded once, reused across all scrape runs ──────────────

@lru_cache(maxsize=1)
def _get_model():
    """Load sentence-transformer model. Cached after first call."""
    from sentence_transformers import SentenceTransformer
    logger.info("bert_scorer: loading model %s", BERT_MODEL_NAME)
    model = SentenceTransformer(BERT_MODEL_NAME)
    logger.info("bert_scorer: model ready")
    return model


def _build_profile_text(
    skills: list[str],
    broad_category: str,
    sub_categories: list[str],
    work_experience: list,
    raw_context: str | None,
) -> str:
    """
    Build the candidate representation used for embedding.
    Prioritises the highest-signal fields: skills, target roles, experience titles.
    Falls back to raw_context if structured data is sparse.
    """
    parts: list[str] = []

    if broad_category:
        cats = [broad_category] + list(sub_categories or [])
        parts.append("Target roles: " + ", ".join(cats))

    if skills:
        parts.append("Skills: " + ", ".join(skills[:40]))

    if work_experience:
        for exp in work_experience[:5]:
            if isinstance(exp, dict):
                title   = exp.get("title") or exp.get("role") or ""
                company = exp.get("company") or ""
                summary = exp.get("summary") or exp.get("description") or ""
                if title:
                    parts.append(f"Experience: {title}" + (f" at {company}" if company else ""))
                if summary:
                    parts.append(summary[:300])

    # Fall back to raw CV text if structured fields are thin
    if len("\n".join(parts)) < 200 and raw_context:
        parts.append(raw_context[:2000])

    return "\n".join(parts)


def _encode_sync(texts: list[str]) -> "list":
    """Synchronous encode — called via asyncio.to_thread() to avoid blocking the event loop."""
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True, batch_size=32)


def _cosine_similarities_sync(profile_emb, job_embs) -> "list[float]":
    """Cosine similarity calculation — also CPU-bound, run in thread."""
    from sklearn.metrics.pairwise import cosine_similarity
    sims = cosine_similarity([profile_emb], job_embs)[0]
    return [float(s) for s in sims]


# ── Public API ────────────────────────────────────────────────────────────────

async def prefilter_jobs(
    jobs: list[dict],
    skills: list[str],
    broad_category: str,
    sub_categories: list[str],
    work_experience: list,
    raw_context: str | None,
) -> tuple[list[dict], list[dict]]:
    """
    Stage 1: BERT pre-filter.

    Encodes the candidate profile and all jobs, computes cosine similarity,
    and splits jobs into:
      - candidates  (sim >= BERT_PASS_THRESHOLD) → proceed to LLM
      - skipped     (sim <  BERT_PASS_THRESHOLD) → SKIP, zero LLM cost

    All CPU-bound encoding runs in asyncio.to_thread() per Section 4.5.

    Returns (candidates, skipped). Each job dict gets a 'bert_sim' key added.
    """
    if not jobs:
        return [], []

    profile_text = _build_profile_text(skills, broad_category, sub_categories, work_experience, raw_context)
    logger.debug("bert_scorer: profile text length=%d", len(profile_text))

    # Encode profile + all jobs concurrently (both CPU-bound)
    job_texts = [
        f"{j.get('title', '')} at {j.get('company', '')}. {j.get('description', '')[:800]}"
        for j in jobs
    ]

    profile_emb, job_embs = await asyncio.gather(
        asyncio.to_thread(_encode_sync, [profile_text]),
        asyncio.to_thread(_encode_sync, job_texts),
    )
    profile_emb = profile_emb[0]

    sims = await asyncio.to_thread(_cosine_similarities_sync, profile_emb, job_embs)

    candidates: list[dict] = []
    skipped: list[dict]    = []

    for job, sim in zip(jobs, sims):
        entry = {**job, "bert_sim": round(sim, 4)}
        if sim >= BERT_PASS_THRESHOLD:
            candidates.append(entry)
        else:
            skipped.append(entry)

    logger.info(
        "bert_scorer: prefilter complete — %d candidates / %d skipped (threshold=%.2f)",
        len(candidates), len(skipped), BERT_PASS_THRESHOLD,
    )
    return candidates, skipped
