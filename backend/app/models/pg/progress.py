# backend/app/models/pg/progress.py
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, ForeignKey  # ForeignKey kept for user_id
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)  # logical link — FK dropped in migration h2i3j4k5l6m7
    career_track: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0–10.0
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
