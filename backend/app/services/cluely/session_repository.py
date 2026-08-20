"""
Write-through repository for cluely overlay sessions (SQLite or PostgreSQL).

Design principles:
- Session start/end and interactions write immediately (low volume, high value).
- Transcript lines are micro-batched: rows accumulate in an asyncio.Queue and
  a background flusher drains the queue every FLUSH_INTERVAL_MS milliseconds
  using a single bulk INSERT. This avoids one round-trip per spoken word while
  still guaranteeing near-real-time persistence.
- All DB access is async via SQLAlchemy async session (aiosqlite or asyncpg).
- No business logic here — pure repository pattern.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pg.cluely_session import CluelySession, CluelyTranscriptLine, CluelyInteraction

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_MS = 50   # drain transcript queue this often
FLUSH_BATCH_MAX   = 200  # maximum rows per bulk INSERT


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._queue: asyncio.Queue[CluelyTranscriptLine] = asyncio.Queue()
        self._flush_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        company: str,
        role: str,
        title: str | None = None,
        application_id: str | None = None,
        session_type: str | None = None,
    ) -> None:
        await self._db.execute(
            text("""
                INSERT INTO cluely_sessions
                    (id, user_id, company, role, title, application_id, session_type, tools_used, started_at)
                VALUES
                    (:id, :user_id, :company, :role, :title, :application_id, :session_type, :tools_used, :started_at)
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": session_id,
                "user_id": user_id,
                "company": company,
                "role": role,
                "title": title or _auto_title(company, role),
                "application_id": application_id,
                "session_type": session_type,
                "tools_used": "[]",
                "started_at": _utcnow(),
            },
        )
        await self._db.commit()
        logger.info("[repo] session created | id=%s type=%s", session_id, session_type)

    async def get_session_owner(self, session_id: str) -> str | None:
        """Return the user_id that owns session_id, or None if it doesn't exist."""
        try:
            result = await self._db.execute(
                text("SELECT user_id FROM cluely_sessions WHERE id = :id"),
                {"id": session_id},
            )
            row = result.fetchone()
            return str(row.user_id) if row else None
        except Exception as e:
            logger.warning("[repo] get_session_owner failed: %s", e)
            return None

    async def record_tool_used(self, session_id: str, tool: str) -> None:
        """Append a tool name to the tools_used JSON array if not already present."""
        try:
            # Fetch current value, update in Python, write back — avoids JSONB cast issues
            result = await self._db.execute(
                text("SELECT tools_used FROM cluely_sessions WHERE id = :id"),
                {"id": session_id},
            )
            row = result.fetchone()
            if row is None:
                return
            current = row.tools_used
            if isinstance(current, str):
                import json as _json
                current = _json.loads(current)
            if not isinstance(current, list):
                current = []
            if tool not in current:
                current.append(tool)
                import json as _json
                await self._db.execute(
                    text("UPDATE cluely_sessions SET tools_used = :val WHERE id = :id"),
                    {"val": _json.dumps(current), "id": session_id},
                )
                await self._db.commit()
        except Exception as e:
            logger.warning("[repo] record_tool_used failed: %s", e)
            try:
                await self._db.rollback()
            except Exception:
                pass

    async def end_session(self, session_id: str, post_summary: str | None = None) -> None:
        # Flush any remaining transcript lines before closing
        await self._flush_queue()

        now = _utcnow()
        result = await self._db.execute(
            text("SELECT started_at FROM cluely_sessions WHERE id = :id"),
            {"id": session_id},
        )
        row = result.fetchone()
        duration = None
        if row and row.started_at:
            started = row.started_at
            if isinstance(started, str):
                from datetime import datetime
                started = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
            delta = now - started
            duration = int(delta.total_seconds())

        await self._db.execute(
            text(
                "UPDATE cluely_sessions "
                "SET ended_at = :ended_at, duration_seconds = :dur, post_summary = :summary "
                "WHERE id = :id"
            ),
            {"ended_at": now, "dur": duration, "summary": post_summary, "id": session_id},
        )
        await self._db.commit()
        logger.info("[repo] session ended | id=%s | duration=%ss", session_id, duration)

    # ------------------------------------------------------------------
    # Transcript lines — micro-batched
    # ------------------------------------------------------------------

    async def append_transcript_line(
        self,
        session_id: str,
        speaker: str,
        text_content: str,
        seq: int,
        spoken_at: datetime | None = None,
    ) -> None:
        line = CluelyTranscriptLine(
            id=_new_id(),
            session_id=session_id,
            speaker=speaker,
            text=text_content,
            seq=seq,
            spoken_at=spoken_at or _utcnow(),
        )
        await self._queue.put(line)

    def start_flush_loop(self) -> None:
        """Launch the background micro-batch flusher. Call once per session."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_loop())

    def stop_flush_loop(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

    async def _flush_loop(self) -> None:
        interval = FLUSH_INTERVAL_MS / 1000.0
        try:
            while True:
                await asyncio.sleep(interval)
                await self._flush_queue()
        except asyncio.CancelledError:
            await self._flush_queue()  # final drain

    async def _flush_queue(self) -> None:
        batch: list[CluelyTranscriptLine] = []
        try:
            while len(batch) < FLUSH_BATCH_MAX:
                batch.append(self._queue.get_nowait())
        except asyncio.QueueEmpty:
            pass
        if not batch:
            return
        self._db.add_all(batch)
        try:
            await self._db.commit()
            logger.debug("[repo] flushed %d transcript lines", len(batch))
        except Exception as e:
            logger.error("[repo] transcript flush failed: %s", e)
            await self._db.rollback()

    # ------------------------------------------------------------------
    # Interactions — write-through immediately
    # ------------------------------------------------------------------

    async def append_interaction(
        self,
        session_id: str,
        trigger_type: str,
        ai_response: str,
        question_text: str | None = None,
        inferred_outcome: str | None = None,
        mode: str | None = None,
    ) -> None:
        row = CluelyInteraction(
            id=_new_id(),
            session_id=session_id,
            trigger_type=trigger_type,
            question_text=question_text,
            inferred_outcome=inferred_outcome,
            ai_response=ai_response,
            mode=mode,
            occurred_at=_utcnow(),
        )
        try:
            # Rollback any aborted transaction before writing (defensive)
            await self._db.rollback()
        except Exception:
            pass
        self._db.add(row)
        try:
            await self._db.commit()
        except Exception as e:
            logger.error("[repo] interaction write failed: %s", e)
            try:
                await self._db.rollback()
            except Exception:
                pass


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _auto_title(company: str, role: str) -> str:
    parts = []
    if role:
        parts.append(role)
    if company:
        parts.append(f"at {company}")
    return " ".join(parts) if parts else "Overlay Session"
