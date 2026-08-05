from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, DateTime, Boolean, Float, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False)  # no FK — logical link only
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    time_budget_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hard_cutoff_fired: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)


class SimulationTurn(Base):
    __tablename__ = "simulation_turns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String, nullable=False)  # logical FK to simulation_sessions
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)   # "user" | "ai"
    modality: Mapped[str] = mapped_column(String(10), nullable=False)  # "voice" | "text"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    time_offset_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tool_calls: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    emotion_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rewrite_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class SimulationDebrief(Base):
    __tablename__ = "simulation_debriefs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String, nullable=False)  # logical FK
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hire_signal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    core_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scenario_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    improvements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    focus_areas: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
