import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, Date, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MeetingDebrief(Base):
    """
    One debrief record per (user, calendar event).
    Notes, actions, and decisions are persisted here and updated in near-realtime
    via PATCH calls from the dashboard. AI summary is generated on demand.
    """
    __tablename__ = "meeting_debriefs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False)

    # CalDAV VEVENT UID — stable across edits, used to deduplicate
    calendar_event_uid: Mapped[str | None] = mapped_column(String(512), nullable=True)

    date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="Untitled meeting")
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)   # "HH:MM" UTC
    duration_minutes: Mapped[int | None] = mapped_column(String, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # [{text, owner, due, done}]
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # [{text, meta}]
    decisions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # [{name, email, role, initials, color, status}]
    attendees: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Linked Cluely overlay session — transcript is pulled in for AI summary
    cluely_session_id: Mapped[str | None] = mapped_column(String, nullable=True)

    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # none | pending | done | error
    ai_summary_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_meeting_debriefs_user_id", "user_id"),
        Index("ix_meeting_debriefs_user_date", "user_id", "date"),
    )
