# backend/app/services/job_hunter/deduplicator.py
"""
In-run job deduplication.

Two jobs are considered duplicates if they share the same normalised
company + title fingerprint — regardless of which board they came from.

This is separate from the DB-level url_hash dedup (which handles
cross-run duplicates via a unique constraint). This module handles
within-run duplicates before anything hits the DB.
"""
from __future__ import annotations

import re
import unicodedata


def _normalise(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace, remove punctuation."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_TITLE_NOISE = re.compile(
    r"\b(sr|senior|jr|junior|lead|staff|principal|associate|mid|i|ii|iii|iv)\b"
)


def _title_key(title: str) -> str:
    """Strip level prefixes so 'Senior Backend Engineer' == 'Backend Engineer'."""
    return _TITLE_NOISE.sub("", _normalise(title)).strip()


def fingerprint(job: dict) -> str:
    """Return a dedup key for a raw job dict."""
    company = _normalise(job.get("company") or "")
    title   = _title_key(job.get("title") or "")
    return f"{company}|{title}"


def deduplicate(jobs: list[dict]) -> list[dict]:
    """
    Remove duplicate jobs from a mixed list (across boards).

    Keeps the first occurrence of each fingerprint. Boards should be
    ordered by priority before calling this so the highest-quality
    source wins on collision.

    Returns a new list — input is not mutated.
    """
    seen: set[str] = set()
    result: list[dict] = []
    for job in jobs:
        key = fingerprint(job)
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result
