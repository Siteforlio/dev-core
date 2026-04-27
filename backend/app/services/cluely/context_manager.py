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
        self._state_key = f"cluely:session:{session_id}:state"

    async def push_transcript(self, entry: TranscriptEntry) -> None:
        await self._r.rpush(self._transcript_key, entry.model_dump_json())
        await self._r.ltrim(self._transcript_key, -20, -1)  # keep last 20
        await self._r.expire(self._transcript_key, TRANSCRIPT_TTL)

    async def get_window(self, n: int = 10) -> list[TranscriptEntry]:
        raw = await self._r.lrange(self._transcript_key, -n, -1)
        return [TranscriptEntry(**json.loads(r)) for r in raw]

    async def set_state(self, state: str) -> None:
        await self._r.setex(self._state_key, TRANSCRIPT_TTL, state)

    async def get_state(self) -> str | None:
        val = await self._r.get(self._state_key)
        return val.decode() if val else None

    async def session_exists(self) -> bool:
        return bool(await self._r.exists(self._state_key))
