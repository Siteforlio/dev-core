# backend/app/models/pg/knowledge.py
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class KnowledgeProfile(Base):
    __tablename__ = "knowledge_profiles"
    __table_args__ = (UniqueConstraint("track", "level", "stage", name="uq_knowledge_profile"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    track: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
