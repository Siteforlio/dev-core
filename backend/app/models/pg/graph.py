"""SQLAlchemy models for the graph layer (companies, managers, rounds, questions, community rounds).

These replace the Neo4j graph database used in earlier versions.
"""
import uuid
from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


class Company(Base):
    __tablename__ = "graph_companies"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Manager(Base):
    __tablename__ = "graph_managers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("graph_companies.name"), nullable=True
    )
    traits: Mapped[list | None] = mapped_column(JSON, nullable=True)  # stored as JSON array


class InterviewRound(Base):
    __tablename__ = "graph_interview_rounds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name: Mapped[str] = mapped_column(
        String(255), ForeignKey("graph_companies.name"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_name", "type", name="uq_interview_round_company_type"),
        Index("ix_interview_rounds_company", "company_name"),
    )


class InterviewQuestion(Base):
    __tablename__ = "graph_interview_questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    round_id: Mapped[str] = mapped_column(
        String, ForeignKey("graph_interview_rounds.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        Index("ix_interview_questions_round", "round_id"),
    )


class CommunityRound(Base):
    __tablename__ = "graph_community_rounds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    round_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_grade: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_name", "role", "round_type", name="uq_community_round"),
        Index("ix_community_rounds_company", "company_name"),
    )
