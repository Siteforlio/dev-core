import json
import logging
from app.schemas.cluely import TranscriptEntry

logger = logging.getLogger(__name__)
TRANSCRIPT_TTL = 4 * 3600  # 4 hours


class ContextManager:
    def __init__(self, redis, session_id: str):
        self._r = redis
        self._sid = session_id
        self._transcript_key = f"cluely:session:{session_id}:transcript"
        self._state_key      = f"cluely:session:{session_id}:state"
        self._summary_key    = f"cluely:session:{session_id}:summary"
        self._facts_key      = f"cluely:session:{session_id}:facts"
        self._summarized_key = f"cluely:session:{session_id}:summarized_up_to"

    async def push_transcript(self, entry: TranscriptEntry) -> None:
        length = await self._r.rpush(self._transcript_key, entry.model_dump_json())
        if length == 1:
            await self._r.expire(self._transcript_key, TRANSCRIPT_TTL)
        # No ltrim — keep the full transcript for context

    async def get_window(self, n: int = 15) -> list[TranscriptEntry]:
        """Return the most recent n bubbles verbatim."""
        raw = await self._r.lrange(self._transcript_key, -n, -1)
        return [TranscriptEntry(**json.loads(r)) for r in raw]

    async def get_all_since(self, index: int) -> list[TranscriptEntry]:
        """Return all bubbles from index onwards (for incremental summarisation)."""
        raw = await self._r.lrange(self._transcript_key, index, -1)
        return [TranscriptEntry(**json.loads(r)) for r in raw]

    async def get_total_count(self) -> int:
        return await self._r.llen(self._transcript_key)

    async def get_summarized_index(self) -> int:
        val = await self._r.get(self._summarized_key)
        return int(val) if val else 0

    async def set_summarized_index(self, index: int) -> None:
        await self._r.setex(self._summarized_key, TRANSCRIPT_TTL, index)

    async def get_summary(self) -> str:
        val = await self._r.get(self._summary_key)
        if not val:
            return ""
        return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

    async def set_summary(self, text: str) -> None:
        await self._r.setex(self._summary_key, TRANSCRIPT_TTL, text)

    async def get_facts(self) -> str:
        val = await self._r.get(self._facts_key)
        if not val:
            return ""
        return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

    async def set_facts(self, text: str) -> None:
        await self._r.setex(self._facts_key, TRANSCRIPT_TTL, text)

    async def set_state(self, state: str) -> None:
        await self._r.setex(self._state_key, TRANSCRIPT_TTL, state)

    async def get_state(self) -> str | None:
        val = await self._r.get(self._state_key)
        if not val:
            return None
        return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

    async def session_exists(self) -> bool:
        return bool(await self._r.exists(self._state_key))
