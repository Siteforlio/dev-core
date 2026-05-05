from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CluelySession(Base):
    """
    One overlay session per interview. Separate from the interview_prep
    'sessions' table but linked to job_applications when available.
    """
    __tablename__ = "cluely_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    # Optional link to a job application (job_hunter module) — logical link only, no DB FK
    application_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class CluelyTranscriptLine(Base):
    """
    Every spoken line, speaker-labelled, with the sequence number and
    wall-clock timestamp. Full fidelity — never truncated.
    """
    __tablename__ = "cluely_transcript_lines"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("cluely_sessions.id"), nullable=False
    )
    speaker: Mapped[str] = mapped_column(String(20), nullable=False)   # "interviewer" | "user"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    spoken_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class CluelyInteraction(Base):
    """
    Every AI interaction — auto gap-triggered suggestions, manual asks,
    and outcome-pill requests. Used for agent training and session replay.
    """
    __tablename__ = "cluely_interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("cluely_sessions.id"), nullable=False
    )
    # "auto_gap" | "manual_ask" | "outcome_pill"
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_response: Mapped[str] = mapped_column(Text, nullable=False)
    # "hints" | "solve" | "ultra" | null (for auto/pill)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
