# backend/app/services/job_hunter/matcher_service.py
"""
MatcherService — local, free NLP for job fit scoring and skill matching.

Uses sentence-transformers (all-MiniLM-L6-v2, ~80 MB) which runs fully
offline — zero API calls, zero cost.

Replaces 2 of the LLM calls in TailorService:
  pick_top_competencies  →  match_skills(jd, skills, top_n=8)
  pick_resume_skills     →  match_skills(jd, skills, top_n=20)

Adds:
  score_fit(jd_text, profile_text) → float 0.0–1.0
      Pre-filters bad-fit jobs before spending any Gemini quota on them.
      Call this before tailor_for_listing; skip tailoring if score < 0.25.

Model loads once on first use and is reused for the process lifetime.
On a modern CPU the first encode takes ~1 s; subsequent calls ~50 ms.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> "SentenceTransformer":
    """Load the model once and cache it for the process lifetime."""
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("matcher_service: loading %s (first call — ~1 s)", MODEL_NAME)
        model = SentenceTransformer(MODEL_NAME)
        logger.info("matcher_service: model loaded")
        return model
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        )


def _cosine(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity — avoids a numpy import at module level."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class MatcherService:
    """
    Stateless helper — instantiate once and reuse, or call the module-level
    helpers directly (they share the same cached model).
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def score_fit(self, jd_text: str, profile_text: str) -> float:
        """
        Semantic similarity between the job description and a plain-text
        summary of the candidate's profile.

        Returns a float in [0, 1].  Typical thresholds:
          < 0.20 → very poor fit, skip tailoring entirely
          0.20–0.35 → weak fit, tailor only if quota is cheap
          > 0.35 → decent match, proceed normally

        profile_text should be a compact dump of skills + job titles +
        years of experience, e.g.:
          "Python, FastAPI, React, PostgreSQL | Senior Software Engineer
           at Stripe (3 yrs) | 7 years total experience"
        """
        try:
            model = _get_model()
        except Exception as exc:
            logger.warning("matcher_service: score_fit unavailable (%s) — returning 1.0 (no filter)", exc)
            return 1.0  # assume fit when model is unavailable so tailoring still runs
        jd_emb, prof_emb = model.encode(
            [jd_text[:2000], profile_text[:1000]], convert_to_tensor=False
        )
        return float(_cosine(jd_emb.tolist(), prof_emb.tolist()))

    def match_skills(
        self,
        jd_text: str,
        skills: list[str],
        top_n: int = 8,
    ) -> list[str]:
        """
        Return the top-n skills most semantically relevant to the JD.

        Strategy:
          1. Encode the JD and every skill string.
          2. Score each skill by cosine similarity to the JD embedding.
          3. Return the top-n, preserving order from the original list on ties.

        Falls back to skills[:top_n] if the model cannot be loaded.
        """
        if not skills:
            return []
        try:
            model = _get_model()
        except Exception as exc:
            logger.warning("matcher_service: model unavailable (%s) — using first %d skills", exc, top_n)
            return skills[:top_n]

        jd_emb = model.encode(jd_text[:2000], convert_to_tensor=False)
        skill_embs = model.encode(skills, convert_to_tensor=False, batch_size=64)

        scored = [
            (skill, float(_cosine(jd_emb.tolist(), emb.tolist())))
            for skill, emb in zip(skills, skill_embs)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:top_n]]

    def extract_keywords(self, jd_text: str, top_n: int = 15) -> list[str]:
        """
        Extract the most representative keywords from a job description using
        KeyBERT (BERT-powered keyword extraction).

        Falls back gracefully to simple TF-IDF if keybert is unavailable,
        and to an empty list if neither library is present.

        Usage note: this method is an *optional* replacement for the Gemini
        `extract_keywords` call.  The LLM version is often better at picking
        up implicit requirements ("fast-paced startup" → "startup experience"),
        so keep the LLM call for that function and use this only if you need
        to eliminate the API call entirely.
        """
        if not jd_text:
            return []
        try:
            from keybert import KeyBERT
            model = _get_model()
            kw_model = KeyBERT(model=model)
            results = kw_model.extract_keywords(
                jd_text[:3000],
                keyphrase_ngram_range=(1, 2),
                stop_words="english",
                top_n=top_n,
                use_mmr=True,      # Maximal Marginal Relevance — reduces redundancy
                diversity=0.4,
            )
            return [kw for kw, _ in results]
        except ImportError:
            logger.debug("matcher_service: keybert not installed, falling back to TF-IDF keywords")
            return self._tfidf_keywords(jd_text, top_n)
        except Exception as exc:
            logger.warning("matcher_service: extract_keywords failed (%s)", exc)
            return []

    # ── Internal fallback ─────────────────────────────────────────────────────

    @staticmethod
    def _tfidf_keywords(text: str, top_n: int) -> list[str]:
        """Lightweight TF-IDF fallback — no model needed, just sklearn."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import re

            # Split into pseudo-"documents" of 3-word windows so TF-IDF
            # has something meaningful to work with on a single text.
            words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.-]{2,}\b", text)
            if len(words) < 10:
                return words[:top_n]

            chunks = [" ".join(words[i:i + 5]) for i in range(0, len(words) - 4, 2)]
            vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=200)
            mat = vec.fit_transform(chunks)
            scores = mat.sum(axis=0).A1
            vocab = vec.get_feature_names_out()
            ranked = sorted(zip(vocab, scores), key=lambda x: x[1], reverse=True)
            return [w for w, _ in ranked[:top_n]]
        except Exception:
            return []


# Module-level singleton — import and use directly where convenient
matcher = MatcherService()
