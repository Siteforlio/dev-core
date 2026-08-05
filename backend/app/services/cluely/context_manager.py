import json
import logging
from app.schemas.cluely import TranscriptEntry
from app.core.cache import cache_set, cache_get, cache_delete, SESSION_TTL

logger = logging.getLogger(__name__)
TRANSCRIPT_TTL = SESSION_TTL  # 4 hours


class ContextManager:
    def __init__(self, session_id: str):
        self._sid = session_id
        self._transcript_key = f"cluely:session:{session_id}:transcript"
        self._state_key      = f"cluely:session:{session_id}:state"
        self._summary_key    = f"cluely:session:{session_id}:summary"
        self._facts_key      = f"cluely:session:{session_id}:facts"
        self._summarized_key = f"cluely:session:{session_id}:summarized_up_to"

    async def push_transcript(self, entry: TranscriptEntry) -> None:
        existing = await cache_get(self._transcript_key) or []
        existing.append(entry.model_dump())
        await cache_set(self._transcript_key, existing, ttl=TRANSCRIPT_TTL)

    async def get_window(self, n: int = 15) -> list[TranscriptEntry]:
        """Return the most recent n bubbles verbatim."""
        all_entries = await cache_get(self._transcript_key) or []
        return [TranscriptEntry(**e) for e in all_entries[-n:]]

    async def get_all_since(self, index: int) -> list[TranscriptEntry]:
        """Return all bubbles from index onwards (for incremental summarisation)."""
        all_entries = await cache_get(self._transcript_key) or []
        return [TranscriptEntry(**e) for e in all_entries[index:]]

    async def get_total_count(self) -> int:
        all_entries = await cache_get(self._transcript_key) or []
        return len(all_entries)

    async def get_summarized_index(self) -> int:
        val = await cache_get(self._summarized_key)
        return val.get("index", 0) if val else 0

    async def set_summarized_index(self, index: int) -> None:
        await cache_set(self._summarized_key, {"index": index}, ttl=TRANSCRIPT_TTL)

    async def get_summary(self) -> str:
        val = await cache_get(self._summary_key)
        return val.get("text", "") if val else ""

    async def set_summary(self, text: str) -> None:
        await cache_set(self._summary_key, {"text": text}, ttl=TRANSCRIPT_TTL)

    async def get_facts(self) -> str:
        val = await cache_get(self._facts_key)
        return val.get("text", "") if val else ""

    async def set_facts(self, text: str) -> None:
        await cache_set(self._facts_key, {"text": text}, ttl=TRANSCRIPT_TTL)

    async def set_state(self, state: str) -> None:
        await cache_set(self._state_key, {"state": state}, ttl=TRANSCRIPT_TTL)

    async def get_state(self) -> str | None:
        val = await cache_get(self._state_key)
        return val.get("state") if val else None

    async def session_exists(self) -> bool:
        return await cache_get(self._state_key) is not None
