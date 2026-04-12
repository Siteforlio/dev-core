# backend/app/models/pg/job_hunter.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, Text, Index, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class JobHunterProfile(Base):
    __tablename__ = "job_hunter_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_score: Mapped[int] = mapped_column(Integer, default=0)
    work_experience: Mapped[list] = mapped_column(JSONB, default=list)
    education: Mapped[list] = mapped_column(JSONB, default=list)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    projects: Mapped[list] = mapped_column(JSONB, default=list)
    languages_spoken: Mapped[list] = mapped_column(JSONB, default=list)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_job_hunter_profiles_user_id", "user_id"),
        UniqueConstraint("user_id", name="uq_job_hunter_profiles_user_id"),
    )

class JobHunterCampaign(Base):
    __tablename__ = "job_hunter_campaigns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    broad_category: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_categories: Mapped[list] = mapped_column(JSONB, default=list)
    profile_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    email_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    caldav_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_monitor_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    schedule_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    user_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_jh_campaigns_user_id", "user_id"),
        Index("ix_jh_campaigns_user_status", "user_id", "status"),
    )

class JobListing(Base):
    __tablename__ = "job_listings"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("job_hunter_campaigns.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sub_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_job_listings_url_hash"),
        Index("ix_job_listings_campaign_status", "campaign_id", "status"),
        Index("ix_job_listings_campaign_category", "campaign_id", "sub_category"),
        Index("ix_job_listings_url_hash", "url_hash"),
    )

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("job_hunter_campaigns.id"), nullable=False)
    job_listing_id: Mapped[str] = mapped_column(String, ForeignKey("job_listings.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    tailored_resume_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("job_listing_id", "user_id", name="uq_applications_listing_user"),
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_job_listing", "job_listing_id"),
        Index("ix_applications_campaign", "campaign_id"),
    )

class EmailEvent(Base):
    __tablename__ = "email_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str | None] = mapped_column(String, ForeignKey("applications.id"), nullable=True)
    campaign_id: Mapped[str] = mapped_column(String, ForeignKey("job_hunter_campaigns.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reply_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reply_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reply_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_email_events_campaign_type", "campaign_id", "type"),
        Index("ix_email_events_application", "application_id"),
    )

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(String, ForeignKey("applications.id"), nullable=False)
    email_event_id: Mapped[str] = mapped_column(String, ForeignKey("email_events.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    calendar_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_calendar_events_application", "application_id"),)
