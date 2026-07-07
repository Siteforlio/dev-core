"""
MeetingDebriefService — get-or-create, patch, and AI summary generation
for the realtime debrief dashboard.

Layering (ARCHITECTURE.md §4.2):
  Route handler → this service → DB only.
  No raw SQL here — SQLAlchemy ORM exclusively.
"""
import logging
from datetime import datetime, timezone, date as date_type

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pg.meeting_debrief import MeetingDebrief

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(date_str: str | None) -> date_type | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).date()
    except ValueError:
        return None


class MeetingDebriefService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(
        self,
        user_id: str,
        calendar_event_uid: str | None,
        date_str: str | None,
        title: str,
        location: str | None = None,
        start_time: str | None = None,
        duration_minutes: int | None = None,
        attendees: list[dict] | None = None,
    ) -> MeetingDebrief:
        """
        Return existing debrief for this (user, calendar_event_uid) pair.
        Create a new one if it doesn't exist yet.
        Falls back to matching by (user_id, date, title) when uid is absent.
        """
        row: MeetingDebrief | None = None

        if calendar_event_uid:
            result = await self.db.execute(
                select(MeetingDebrief).where(
                    MeetingDebrief.user_id == user_id,
                    MeetingDebrief.calendar_event_uid == calendar_event_uid,
                )
            )
            row = result.scalar_one_or_none()

        if row is None and date_str:
            parsed = _parse_date(date_str)
            result = await self.db.execute(
                select(MeetingDebrief).where(
                    MeetingDebrief.user_id == user_id,
                    MeetingDebrief.date == parsed,
                    MeetingDebrief.title == title,
                )
            )
            row = result.scalar_one_or_none()

        if row is None:
            row = MeetingDebrief(
                user_id=user_id,
                calendar_event_uid=calendar_event_uid,
                date=_parse_date(date_str),
                title=title,
                location=location,
                start_time=start_time,
                duration_minutes=str(duration_minutes) if duration_minutes is not None else None,
                attendees=attendees or [],
                actions=[],
                decisions=[],
                ai_summary_status="none",
            )
            self.db.add(row)
            await self.db.commit()
            await self.db.refresh(row)
        else:
            # Refresh location / attendees if they changed in CalDAV
            changed = False
            if location is not None and row.location != location:
                row.location = location
                changed = True
            if attendees and not row.attendees:
                row.attendees = attendees
                changed = True
            if changed:
                row.updated_at = _utcnow()
                await self.db.commit()
                await self.db.refresh(row)

        return row

    async def get_by_id(self, debrief_id: str, user_id: str) -> MeetingDebrief | None:
        result = await self.db.execute(
            select(MeetingDebrief).where(
                MeetingDebrief.id == debrief_id,
                MeetingDebrief.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_recent(self, user_id: str, limit: int = 20) -> list[MeetingDebrief]:
        result = await self.db.execute(
            select(MeetingDebrief)
            .where(MeetingDebrief.user_id == user_id)
            .order_by(MeetingDebrief.date.desc(), MeetingDebrief.start_time.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_date(self, user_id: str, date_str: str) -> list[MeetingDebrief]:
        parsed = _parse_date(date_str)
        if not parsed:
            return []
        result = await self.db.execute(
            select(MeetingDebrief).where(
                MeetingDebrief.user_id == user_id,
                MeetingDebrief.date == parsed,
            ).order_by(MeetingDebrief.start_time)
        )
        return list(result.scalars().all())

    async def patch(
        self,
        debrief_id: str,
        user_id: str,
        notes: str | None = None,
        actions: list[dict] | None = None,
        decisions: list[dict] | None = None,
        attendees: list[dict] | None = None,
        title: str | None = None,
        cluely_session_id: str | None = None,
    ) -> MeetingDebrief | None:
        row = await self.get_by_id(debrief_id, user_id)
        if not row:
            return None

        if notes is not None:
            row.notes = notes
        if actions is not None:
            row.actions = actions
        if decisions is not None:
            row.decisions = decisions
        if attendees is not None:
            row.attendees = attendees
        if title is not None:
            row.title = title
        if cluely_session_id is not None:
            row.cluely_session_id = cluely_session_id

        row.updated_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def generate_ai_summary(self, debrief_id: str, user_id: str) -> MeetingDebrief | None:
        """
        Call DeepSeek to generate a meeting summary and extract action items /
        decisions from the transcript. Sets ai_summary_status = 'pending'
        immediately, then updates to 'done' or 'error'.
        """
        row = await self.get_by_id(debrief_id, user_id)
        if not row:
            return None

        row.ai_summary_status = "pending"
        row.updated_at = _utcnow()
        await self.db.commit()

        try:
            result = await self._call_deepseek(row)
            row.ai_summary = result.get("summary", "")
            # Only overwrite actions/decisions when the AI found something
            if result.get("actions"):
                row.actions = result["actions"]
            if result.get("decisions"):
                row.decisions = result["decisions"]
            row.ai_summary_status = "done"
        except Exception:
            logger.exception("AI summary generation failed for debrief %s", debrief_id)
            row.ai_summary_status = "error"

        row.updated_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def compose_followup_email(self, debrief_id: str, user_id: str) -> dict | None:
        """
        Use DeepSeek to compose a contextually appropriate follow-up email.
        The AI reads the meeting transcript, notes, summary, and meeting type
        to decide on tone, content, and structure — not a fixed template.
        """
        import json as _json
        from app.services.job_hunter.llm import call_llm
        from sqlalchemy import select as sa_select
        from app.models.pg.cluely_session import CluelyTranscriptLine

        row = await self.get_by_id(debrief_id, user_id)
        if not row:
            return None

        notes_text      = row.notes or "(no notes captured)"
        ai_summary      = row.ai_summary or "(no summary yet)"
        attendees_text  = ", ".join(a.get("name", "") for a in (row.attendees or [])) or "the team"
        actions_text    = "\n".join(
            f"- {a.get('text','')} (owner: {a.get('owner','TBD')}, due: {a.get('due','ASAP')})"
            for a in (row.actions or [])
        ) or "(none identified)"
        decisions_text  = "\n".join(f"- {d.get('text','')}" for d in (row.decisions or [])) or "(none recorded)"

        transcript_section = ""
        if row.cluely_session_id:
            result = await self.db.execute(
                sa_select(CluelyTranscriptLine)
                .where(CluelyTranscriptLine.session_id == row.cluely_session_id)
                .order_by(CluelyTranscriptLine.seq)
            )
            lines = result.scalars().all()
            if lines:
                transcript_section = "\nFull transcript:\n" + "\n".join(
                    f"[{ln.speaker}] {ln.text}" for ln in lines
                ) + "\n"

        prompt = f"""You are a professional assistant composing a follow-up email after a meeting.

Meeting: {row.title}
Date: {row.date}
Attendees: {attendees_text}

Summary: {ai_summary}

Notes:
{notes_text}
{transcript_section}
Action items:
{actions_text}

Decisions:
{decisions_text}

Instructions:
- Read the meeting content carefully and determine what KIND of meeting this was (sales pitch, partnership discussion, technical review, internal sync, client call, etc.)
- Choose the appropriate professional tone and structure for that meeting type
- Reference SPECIFIC things that were discussed — names, topics, outcomes, next steps
- Do NOT use generic filler like "Thanks for your time" or "Hope this finds you well"
- The email should feel like it was written by someone who was actually in that meeting
- If there are action items, list them clearly with owners
- Keep it concise and professional

Return ONLY valid JSON, no markdown:
{{
  "subject": "concise subject line referencing the specific meeting topic",
  "body": "full email body, properly formatted with line breaks"
}}"""

        raw = await call_llm(prompt, max_tokens=700, json_mode=True)
        try:
            return _json.loads(raw)
        except Exception:
            return {"subject": f"{row.title} — Follow-up", "body": raw}

    async def _call_deepseek(self, row: MeetingDebrief) -> dict:
        import json as _json
        from app.services.job_hunter.llm import call_llm
        from sqlalchemy import select as sa_select
        from app.models.pg.cluely_session import CluelyTranscriptLine

        notes_text = row.notes or "(no notes captured)"
        attendees_text = ", ".join(a.get("name", "") for a in (row.attendees or [])) or "(unknown)"

        # Pull transcript if session is linked
        transcript_section = ""
        if row.cluely_session_id:
            result = await self.db.execute(
                sa_select(CluelyTranscriptLine)
                .where(CluelyTranscriptLine.session_id == row.cluely_session_id)
                .order_by(CluelyTranscriptLine.seq)
            )
            lines = result.scalars().all()
            if lines:
                transcript_section = "\nFull session transcript:\n" + "\n".join(
                    f"[{ln.speaker}] {ln.text}" for ln in lines
                ) + "\n"

        prompt = f"""You are analysing a meeting for a professional debrief dashboard.

Meeting: {row.title}
Date: {row.date}
Attendees: {attendees_text}

Notes:
{notes_text}
{transcript_section}
Extract the following and return ONLY valid JSON — no markdown, no code fences:
{{
  "summary": "3-5 sentence executive summary of outcomes, risks, and next steps",
  "actions": [
    {{"text": "specific action item", "owner": "person name or TBD", "due": "date or ASAP", "done": false}}
  ],
  "decisions": [
    {{"text": "decision made", "meta": "brief context"}}
  ]
}}

If there are no actions or decisions, return empty arrays. Be specific — no generic filler."""

        raw = await call_llm(prompt, max_tokens=800, json_mode=True)
        try:
            return _json.loads(raw)
        except Exception:
            # Fallback: treat the whole response as a plain summary
            return {"summary": raw, "actions": [], "decisions": []}
