import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.pg.job_hunter import CalendarEvent
from app.core.config import settings
from app.services.job_hunter.llm import call_llm

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _call_haiku(self, prompt: str) -> str:
        return await call_llm(prompt, max_tokens=100)

    async def extract_interview_datetime(self, email_body: str) -> dict:
        raw = await self._call_haiku(
            f'Extract interview date/time from this email. Return JSON: {{"date": "YYYY-MM-DD", "time": "HH:MM", "duration_minutes": N}}. '
            f"If unknown, use duration_minutes: 60.\nEmail: {email_body[:1000]}"
        )
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {"date": None, "time": None, "duration_minutes": 60}
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return {"date": None, "time": None, "duration_minutes": 60}

    async def _push_caldav_event(self, creds: dict, title: str, scheduled_at: datetime, duration_minutes: int) -> str | None:
        try:
            import asyncio
            import caldav

            def _push():
                client = caldav.DAVClient(
                    url=creds["url"],
                    username=creds.get("username"),
                    password=creds.get("password"),
                )
                principal = client.principal()
                calendars = principal.calendars()
                if not calendars:
                    return None
                cal = calendars[0]
                end_dt = scheduled_at + timedelta(minutes=duration_minutes)
                ical = (
                    f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
                    f"BEGIN:VEVENT\r\nSUMMARY:{title}\r\n"
                    f"DTSTART:{scheduled_at.strftime('%Y%m%dT%H%M%SZ')}\r\n"
                    f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%SZ')}\r\n"
                    f"END:VEVENT\r\nEND:VCALENDAR\r\n"
                )
                event = cal.save_event(ical)
                return str(event.url)

            return await asyncio.to_thread(_push)
        except Exception:
            logger.exception("_push_caldav_event failed for %s", creds.get("url"))
            return None

    @staticmethod
    def _sanitize_ical_text(value: str) -> str:
        """Strip CR and LF to prevent iCalendar header injection."""
        return value.replace("\r", "").replace("\n", "")

    async def create_interview_event(
        self,
        application_id: str,
        email_event_id: str,
        company: str,
        role: str,
        scheduled_at: datetime,
        duration_minutes: int,
        caldav_creds: dict,
    ) -> CalendarEvent:
        title = self._sanitize_ical_text(f"Interview: {role[:150]} at {company[:100]}")
        ext_id = await self._push_caldav_event(caldav_creds, title, scheduled_at, duration_minutes)
        event = CalendarEvent(
            id=str(uuid.uuid4()),
            application_id=application_id,
            email_event_id=email_event_id,
            title=title,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            calendar_provider="caldav",
            external_event_id=ext_id,
        )
        self.db.add(event)
        await self.db.commit()
        return event
