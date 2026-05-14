from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Float, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class InterviewSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    career_track: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    interview_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    jd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, nullable=True)
    time_budget_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

class RoundMoment(Base):
    __tablename__ = "round_moments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    round_id: Mapped[str] = mapped_column(String, ForeignKey("rounds.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    emotion_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rewrite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class InterviewProfile(Base):
    __tablename__ = "interview_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
