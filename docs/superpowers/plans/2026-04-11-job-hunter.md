# Job Hunter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully automated job search engine that scrapes 100+ jobs/day, tailors resumes to 90%+ match, auto-applies, monitors email, syncs calendar, and bridges into the existing Interview Prep module.

**Architecture:** FastAPI backend with Celery workers (Redis broker), JobSpy + Crawlee for scraping, Claude Haiku for filtering/tailoring, Playwright for ATS form submission, IMAP/SMTP for email, CalDAV for calendar. All job hunter tables in existing PostgreSQL instance. Existing PersonaEngine/Neo4j graph reused read-only for Interview Prep bridge.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, Celery[redis], JobSpy, Crawlee[playwright], Anthropic Haiku, pdfplumber, python-docx, cryptography (Fernet), imaplib/smtplib (stdlib), caldav, Redis pub/sub, pytest, AsyncMock

**Reference:** `docs/superpowers/specs/2026-04-11-job-hunter-design.md`, `ARCHITECTURE.md`

---

## File Map

```
backend/
├── app/
│   ├── core/
│   │   ├── celery_app.py                        # CREATE — Celery app + Beat schedule
│   │   └── config.py                            # MODIFY — add new env vars
│   ├── models/pg/
│   │   └── job_hunter.py                        # CREATE — all 6 JH tables
│   ├── schemas/
│   │   └── job_hunter.py                        # CREATE — Pydantic request/response schemas
│   ├── api/v1/job_hunter/
│   │   ├── __init__.py                          # CREATE
│   │   ├── profiles.py                          # CREATE — profile routes
│   │   ├── campaigns.py                         # CREATE — campaign routes
│   │   ├── applications.py                      # CREATE — applications + dashboard routes
│   │   └── ws.py                                # CREATE — WebSocket activity feed
│   ├── services/job_hunter/
│   │   ├── __init__.py                          # CREATE
│   │   ├── profile_service.py                   # CREATE — completeness check, resume parsing
│   │   ├── campaign_service.py                  # CREATE — CRUD, sub-category inference
│   │   ├── scraper_service.py                   # CREATE — JobSpy + Crawlee + dedup + remote filter
│   │   ├── tailor_service.py                    # CREATE — Haiku tailoring, PDF generation
│   │   ├── apply_service.py                     # CREATE — Playwright ATS form filling
│   │   ├── email_service.py                     # CREATE — IMAP polling, classification, SMTP reply
│   │   ├── calendar_service.py                  # CREATE — CalDAV event creation
│   │   ├── dashboard_service.py                 # CREATE — aggregated stats query
│   │   └── bridge_service.py                    # CREATE — Interview Prep handoff
│   ├── workers/
│   │   ├── scraper_worker.py                    # CREATE — Celery task: scrape campaign
│   │   ├── tailor_worker.py                     # CREATE — Celery task: tailor + PDF per listing
│   │   ├── apply_worker.py                      # CREATE — Celery task: submit ATS form
│   │   └── email_worker.py                      # CREATE — Celery Beat task: IMAP poll
│   ├── services/
│   │   └── persona_engine.py                    # MODIFY — add _assemble_context() + get_context()
│   └── main.py                                  # MODIFY — register JH routers
├── migrations/versions/
│   └── <hash>_job_hunter_schema.py              # CREATE via alembic revision
├── tests/
│   ├── services/
│   │   ├── test_profile_service.py              # CREATE
│   │   ├── test_campaign_service.py             # CREATE
│   │   ├── test_scraper_service.py              # CREATE
│   │   ├── test_tailor_service.py               # CREATE
│   │   ├── test_apply_service.py                # CREATE
│   │   ├── test_email_service.py                # CREATE
│   │   ├── test_calendar_service.py             # CREATE
│   │   └── test_bridge_service.py               # CREATE
│   └── api/
│       ├── test_jh_profiles.py                  # CREATE
│       └── test_jh_campaigns.py                 # CREATE
└── requirements.txt                             # MODIFY — add new deps

ARCHITECTURE.md                                  # MODIFY — add Celery to tech stack table
frontend/src/
├── components/job-hunter/
│   ├── CampaignList.tsx                         # CREATE
│   ├── CampaignCreate.tsx                       # CREATE
│   ├── ProfileOnboarding.tsx                    # CREATE
│   └── Dashboard.tsx                            # CREATE
├── hooks/useJobHunter.ts                        # CREATE
└── store/jobHunterStore.ts                      # CREATE
```

---

## Task 1: Foundation — DB Schema, Celery, Config

**Files:**
- Create: `backend/app/models/pg/job_hunter.py`
- Create: `backend/app/core/celery_app.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/requirements.txt`
- Modify: `ARCHITECTURE.md`
- Create migration via `alembic revision --autogenerate`

- [ ] **Step 1: Add dependencies to requirements.txt**

```
jobspy==1.1.8
crawlee[playwright]==0.4.0
celery[redis]==5.4.0
pdfplumber==0.11.0
python-docx==1.1.2
caldav==1.3.9
cryptography==42.0.8
```

Run: `pip install -r backend/requirements.txt`

- [ ] **Step 2: Add env vars to config.py**

```python
# append to Settings class in backend/app/core/config.py
job_hunter_encryption_key: str = ""          # Fernet 32-byte URL-safe base64 key
celery_broker_url: str = "redis://localhost:6379/1"
celery_result_backend: str = "redis://localhost:6379/2"
playwright_max_concurrency: int = 4
```

- [ ] **Step 3: Create celery_app.py**

```python
# backend/app/core/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "job_hunter",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.scraper_worker",
        "app.workers.tailor_worker",
        "app.workers.apply_worker",
        "app.workers.email_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "email-poll-every-60s": {
            "task": "app.workers.email_worker.poll_all_campaigns",
            "schedule": 60.0,
        },
        "scrape-every-6h": {
            "task": "app.workers.scraper_worker.scrape_all_active_campaigns",
            "schedule": 21600.0,
        },
    },
)
```

- [ ] **Step 4: Create job_hunter.py models**

```python
# backend/app/models/pg/job_hunter.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class JobHunterProfile(Base):
    __tablename__ = "job_hunter_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_score: Mapped[int] = mapped_column(Integer, default=0)
    work_experience: Mapped[dict] = mapped_column(JSONB, default=list)
    education: Mapped[dict] = mapped_column(JSONB, default=list)
    skills: Mapped[dict] = mapped_column(JSONB, default=list)
    projects: Mapped[dict] = mapped_column(JSONB, default=list)
    languages_spoken: Mapped[dict] = mapped_column(JSONB, default=list)
    github_url: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class JobHunterCampaign(Base):
    __tablename__ = "job_hunter_campaigns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/paused/completed
    broad_category: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_categories: Mapped[dict] = mapped_column(JSONB, default=list)
    profile_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    email_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    caldav_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_monitor_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    schedule_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    user_country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_jh_campaigns_user_id", "user_id"),
        Index("ix_jh_campaigns_user_status", "user_id", "status"),
    )

class JobListing(Base):
    __tablename__ = "job_listings"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[str | None] = mapped_column(String(10), nullable=True)  # MATCH/PARTIAL/SKIP
    sub_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/tailoring/applying/applied/skipped/failed
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_job_listings_url_hash"),
        Index("ix_job_listings_campaign_status", "campaign_id", "status"),
        Index("ix_job_listings_campaign_category", "campaign_id", "sub_category"),
        Index("ix_job_listings_url_hash", "url_hash"),
    )

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, nullable=False)
    job_listing_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    tailored_resume_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="applied")  # applied/responded/interview/offer/rejected/withdrawn/failed
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_job_listing", "job_listing_id"),
        Index("ix_applications_campaign", "campaign_id"),
    )

class EmailEvent(Base):
    __tablename__ = "email_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str | None] = mapped_column(String, nullable=True)
    campaign_id: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # interview/rejection/other
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
    application_id: Mapped[str] = mapped_column(String, nullable=False)
    email_event_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    calendar_provider: Mapped[str] = mapped_column(String(20), nullable=False)  # google/apple/outlook
    external_event_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    __table_args__ = (Index("ix_calendar_events_application", "application_id"),)
```

- [ ] **Step 5: Generate and run migration**

```bash
cd backend
alembic revision --autogenerate -m "job_hunter_schema"
alembic upgrade head
```

Expected: migration file created, all 6 tables present in DB.

- [ ] **Step 6: Update ARCHITECTURE.md tech stack table** — add row: `| Task queue | Celery + Redis | Latest stable |`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/pg/job_hunter.py backend/app/core/celery_app.py \
        backend/app/core/config.py backend/requirements.txt \
        backend/migrations/versions/ ARCHITECTURE.md
git commit -m "feat(step-1): job hunter foundation — schema, celery, config"
```

---

## Task 2: Profile Onboarding

**Files:**
- Create: `backend/app/services/job_hunter/profile_service.py`
- Create: `backend/app/schemas/job_hunter.py` (profile schemas only)
- Create: `backend/app/api/v1/job_hunter/profiles.py`
- Create: `backend/tests/services/test_profile_service.py`
- Create: `backend/tests/api/test_jh_profiles.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing service tests**

```python
# backend/tests/services/test_profile_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.job_hunter.profile_service import ProfileService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db

async def test_check_completeness_incomplete_returns_missing_fields(mock_db):
    service = ProfileService(mock_db)
    profile_data = {"work_experience": [], "education": [], "skills": [], "projects": [], "languages_spoken": []}
    result = service.check_completeness(profile_data)
    assert result["is_complete"] is False
    assert "work_experience" in result["missing"]

async def test_check_completeness_complete_returns_true(mock_db):
    service = ProfileService(mock_db)
    profile_data = {
        "full_name": "Jane Doe", "email": "jane@example.com", "phone": "+1234567890",
        "city": "London", "country": "GB", "linkedin_url": "https://linkedin.com/in/jane",
        "github_url": "https://github.com/jane",
        "work_experience": [{"company": "Acme", "title": "Engineer", "start_date": "2022-01", "end_date": "Present", "responsibilities": "Built stuff"}],
        "education": [{"degree": "BSc", "institution": "MIT", "field": "CS", "graduation_year": 2021}],
        "skills": ["Python", "Django", "PostgreSQL"],
        "projects": [{"name": "MyApp", "description": "A cool app", "tech_stack": ["Python"], "link": "https://github.com/jane/myapp"}],
        "languages_spoken": [{"language": "English", "proficiency": "Native"}],
    }
    result = service.check_completeness(profile_data)
    assert result["is_complete"] is True
    assert result["missing"] == []

async def test_parse_resume_text_extracts_skills(mock_db):
    service = ProfileService(mock_db)
    resume_text = "Skills: Python, Django, React\nExperience: Software Engineer at Google"
    result = await service.parse_resume_text(resume_text)
    assert isinstance(result, dict)
    assert "skills" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/services/test_profile_service.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement profile_service.py**

```python
# backend/app/services/job_hunter/profile_service.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobHunterProfile
from app.core.config import settings

REQUIRED_FIELDS = {
    "full_name": "Contact: full name",
    "email": "Contact: email",
    "phone": "Contact: phone",
    "city": "Contact: city",
    "country": "Contact: country",
    "linkedin_url": "Contact: LinkedIn URL",
    "github_url": "Contact: GitHub URL",
    "work_experience": "Work experience (min 1 entry)",
    "education": "Education (min 1 entry)",
    "skills": "Skills (min 3)",
    "projects": "Projects (min 1 entry)",
    "languages_spoken": "Languages spoken (min 1)",
}

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def check_completeness(self, data: dict) -> dict:
        missing = []
        for field, label in REQUIRED_FIELDS.items():
            value = data.get(field)
            if not value:
                missing.append(label)
            elif isinstance(value, list) and len(value) == 0:
                missing.append(label)
            elif field == "skills" and isinstance(value, list) and len(value) < 3:
                missing.append(f"{label} (have {len(value)}, need 3)")
        score = int((1 - len(missing) / len(REQUIRED_FIELDS)) * 100)
        return {"is_complete": len(missing) == 0, "missing": missing, "completion_score": score}

    async def parse_resume_text(self, text: str) -> dict:
        """Extract structured profile fields from raw resume text using Haiku."""
        message = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"Extract structured resume data as JSON with keys: full_name, email, phone, city, country, linkedin_url, github_url, work_experience (list), education (list), skills (list of strings), projects (list), languages_spoken (list). Resume text:\n\n{text}"
            }]
        )
        import json
        text_content = message.content[0].text
        start = text_content.find("{")
        end = text_content.rfind("}") + 1
        return json.loads(text_content[start:end])

    async def upsert_profile(self, user_id: str, data: dict) -> JobHunterProfile:
        result = await self.db.execute(
            select(JobHunterProfile).where(JobHunterProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        completeness = self.check_completeness(data)
        if not profile:
            profile = JobHunterProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                is_complete=completeness["is_complete"],
                completion_score=completeness["completion_score"],
                work_experience=data.get("work_experience", []),
                education=data.get("education", []),
                skills=data.get("skills", []),
                projects=data.get("projects", []),
                languages_spoken=data.get("languages_spoken", []),
                github_url=data.get("github_url"),
                linkedin_url=data.get("linkedin_url"),
                portfolio_url=data.get("portfolio_url"),
            )
            self.db.add(profile)
        else:
            for field in ["work_experience", "education", "skills", "projects", "languages_spoken"]:
                if data.get(field):
                    setattr(profile, field, data[field])
            profile.is_complete = completeness["is_complete"]
            profile.completion_score = completeness["completion_score"]
        await self.db.commit()
        return profile
```

- [ ] **Step 4: Create `backend/app/services/job_hunter/__init__.py`** (empty)

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/services/test_profile_service.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 6: Add profile schemas**

```python
# backend/app/schemas/job_hunter.py
from pydantic import BaseModel
from typing import Any

class ProfileUpsertRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    country: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    work_experience: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    skills: list[str] = []
    projects: list[dict[str, Any]] = []
    languages_spoken: list[dict[str, Any]] = []

class ProfileResponse(BaseModel):
    id: str
    user_id: str
    is_complete: bool
    completion_score: int
    missing_fields: list[str] = []

class ResumeTextRequest(BaseModel):
    text: str
```

- [ ] **Step 7: Add profile API routes**

```python
# backend/app/api/v1/job_hunter/profiles.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.services.job_hunter.profile_service import ProfileService
from app.schemas.job_hunter import ProfileUpsertRequest, ProfileResponse, ResumeTextRequest

router = APIRouter(prefix="/job-hunter/profiles", tags=["job-hunter-profiles"])

@router.put("/me", response_model=dict)
async def upsert_profile(
    body: ProfileUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ProfileService(db)
    profile = await service.upsert_profile(current_user.id, body.model_dump())
    completeness = service.check_completeness(body.model_dump())
    return {"data": {"id": profile.id, "is_complete": profile.is_complete,
                     "completion_score": profile.completion_score,
                     "missing_fields": completeness["missing"]}, "error": None}

@router.post("/me/parse-resume", response_model=dict)
async def parse_resume(
    body: ResumeTextRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ProfileService(db)
    extracted = await service.parse_resume_text(body.text)
    return {"data": extracted, "error": None}
```

- [ ] **Step 8: Create `backend/app/api/v1/job_hunter/__init__.py`** (empty)

- [ ] **Step 9: Register router in main.py**

```python
# Add to backend/app/main.py imports:
from app.api.v1.job_hunter.profiles import router as jh_profiles_router
# Add after existing includes:
app.include_router(jh_profiles_router, prefix="/api/v1")
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/job_hunter/ backend/app/schemas/job_hunter.py \
        backend/app/api/v1/job_hunter/ backend/app/main.py \
        backend/tests/services/test_profile_service.py
git commit -m "feat(step-2): profile onboarding — completeness validator, resume parser"
```

---

## Task 3: Campaign Setup

**Files:**
- Create: `backend/app/services/job_hunter/campaign_service.py`
- Create: `backend/app/api/v1/job_hunter/campaigns.py`
- Create: `backend/tests/services/test_campaign_service.py`
- Modify: `backend/app/schemas/job_hunter.py` (add campaign schemas)
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_campaign_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.campaign_service import CampaignService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db

async def test_infer_sub_categories_mobile_dev(mock_db):
    service = CampaignService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='["Mobile Development", "Flutter Development"]')):
        result = await service.infer_sub_categories(
            skills=["Flutter", "Dart", "Firebase"],
            broad_category="Software Engineering"
        )
    assert "Mobile Development" in result

async def test_create_campaign_blocks_incomplete_profile(mock_db):
    service = CampaignService(mock_db)
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=MagicMock(is_complete=False))
    with pytest.raises(ValueError, match="Profile incomplete"):
        await service.create_campaign(user_id="u1", name="Test", broad_category="Engineering", user_country="GB")

async def test_create_campaign_stores_sub_categories(mock_db):
    service = CampaignService(mock_db)
    mock_profile = MagicMock(is_complete=True, skills=["Flutter", "Dart"])
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_profile)
    with patch.object(service, "infer_sub_categories", new=AsyncMock(return_value=["Mobile Development"])):
        campaign = await service.create_campaign(user_id="u1", name="Mobile 2026", broad_category="Software Engineering", user_country="GB")
    assert campaign.sub_categories == ["Mobile Development"]
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd backend && pytest tests/services/test_campaign_service.py -v
```

- [ ] **Step 3: Implement campaign_service.py**

```python
# backend/app/services/job_hunter/campaign_service.py
import uuid, json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobHunterCampaign, JobHunterProfile
from app.core.config import settings

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_haiku(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    async def infer_sub_categories(self, skills: list[str], broad_category: str) -> list[str]:
        prompt = (
            f"Given these skills: {', '.join(skills)} and broad job category: '{broad_category}', "
            f"return a JSON array of specific job sub-categories this person can apply to. "
            f"Examples: Mobile Development, Backend Engineering, Full Stack, DevOps. Max 5 items. JSON array only."
        )
        raw = await self._call_haiku(prompt)
        start, end = raw.find("["), raw.rfind("]") + 1
        return json.loads(raw[start:end])

    async def create_campaign(self, user_id: str, name: str, broad_category: str,
                               user_country: str, profile_overrides: dict | None = None) -> JobHunterCampaign:
        result = await self.db.execute(
            select(JobHunterProfile).where(JobHunterProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if not profile or not profile.is_complete:
            raise ValueError("Profile incomplete — complete all required fields before creating a campaign")

        sub_cats = await self.infer_sub_categories(
            skills=profile.skills or [], broad_category=broad_category
        )
        campaign = JobHunterCampaign(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            status="active",
            broad_category=broad_category,
            sub_categories=sub_cats,
            profile_overrides=profile_overrides or {},
            user_country=user_country.upper()[:2],
            email_monitor_since=_utcnow(),
        )
        self.db.add(campaign)
        await self.db.commit()
        return campaign

    async def list_campaigns(self, user_id: str) -> list[JobHunterCampaign]:
        result = await self.db.execute(
            select(JobHunterCampaign).where(
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def set_status(self, campaign_id: str, status: str) -> None:
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one()
        campaign.status = status
        await self.db.commit()
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd backend && pytest tests/services/test_campaign_service.py -v
```

- [ ] **Step 5: Add campaign schemas + routes**

Add to `backend/app/schemas/job_hunter.py`:
```python
class CampaignCreateRequest(BaseModel):
    name: str
    broad_category: str
    user_country: str  # ISO 3166-1 alpha-2
    profile_overrides: dict[str, Any] = {}

class CampaignResponse(BaseModel):
    id: str
    name: str
    status: str
    broad_category: str
    sub_categories: list[str]
    user_country: str | None
    created_at: str
```

```python
# backend/app/api/v1/job_hunter/campaigns.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.services.job_hunter.campaign_service import CampaignService
from app.schemas.job_hunter import CampaignCreateRequest

router = APIRouter(prefix="/job-hunter/campaigns", tags=["job-hunter-campaigns"])

@router.post("", response_model=dict)
async def create_campaign(body: CampaignCreateRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    service = CampaignService(db)
    campaign = await service.create_campaign(
        user_id=current_user.id, name=body.name,
        broad_category=body.broad_category, user_country=body.user_country,
        profile_overrides=body.profile_overrides,
    )
    return {"data": {"id": campaign.id, "name": campaign.name, "status": campaign.status,
                     "sub_categories": campaign.sub_categories}, "error": None}

@router.get("", response_model=dict)
async def list_campaigns(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    service = CampaignService(db)
    campaigns = await service.list_campaigns(current_user.id)
    return {"data": [{"id": c.id, "name": c.name, "status": c.status, "sub_categories": c.sub_categories} for c in campaigns], "error": None}

@router.patch("/{campaign_id}/status", response_model=dict)
async def update_status(campaign_id: str, body: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    service = CampaignService(db)
    await service.set_status(campaign_id, body["status"])
    return {"data": {"updated": True}, "error": None}
```

- [ ] **Step 6: Register router in main.py**

```python
from app.api.v1.job_hunter.campaigns import router as jh_campaigns_router
app.include_router(jh_campaigns_router, prefix="/api/v1")
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/job_hunter/campaign_service.py \
        backend/app/api/v1/job_hunter/campaigns.py \
        backend/app/schemas/job_hunter.py \
        backend/app/main.py \
        backend/tests/services/test_campaign_service.py
git commit -m "feat(step-3): campaign setup — creation, sub-category inference, status management"
```

---

## Task 4: Job Discovery

**Files:**
- Create: `backend/app/services/job_hunter/scraper_service.py`
- Create: `backend/app/workers/scraper_worker.py`
- Create: `backend/tests/services/test_scraper_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_scraper_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.scraper_service import ScraperService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

async def test_passes_remote_filter(mock_db):
    service = ScraperService(mock_db)
    job = {"remote": True, "location_country": "US"}
    assert service.passes_remote_filter(job, user_country="GB") is True

async def test_blocks_onsite_different_country(mock_db):
    service = ScraperService(mock_db)
    job = {"remote": False, "location_country": "US"}
    assert service.passes_remote_filter(job, user_country="GB") is False

async def test_allows_onsite_same_country(mock_db):
    service = ScraperService(mock_db)
    job = {"remote": False, "location_country": "GB"}
    assert service.passes_remote_filter(job, user_country="GB") is True

async def test_build_url_hash_is_deterministic(mock_db):
    service = ScraperService(mock_db)
    h1 = service.build_url_hash("u1", "Google", "Engineer", "https://apply.google.com/1")
    h2 = service.build_url_hash("u1", "Google", "Engineer", "https://apply.google.com/1")
    assert h1 == h2

async def test_build_url_hash_differs_by_user(mock_db):
    service = ScraperService(mock_db)
    h1 = service.build_url_hash("u1", "Google", "Engineer", "https://apply.google.com/1")
    h2 = service.build_url_hash("u2", "Google", "Engineer", "https://apply.google.com/1")
    assert h1 != h2

async def test_score_job_match_calls_haiku(mock_db):
    service = ScraperService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="MATCH")):
        score = await service.score_job_match(
            title="Flutter Developer", description="Build mobile apps with Flutter",
            sub_categories=["Mobile Development"]
        )
    assert score == "MATCH"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && pytest tests/services/test_scraper_service.py -v
```

- [ ] **Step 3: Implement scraper_service.py**

```python
# backend/app/services/job_hunter/scraper_service.py
import hashlib, uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobListing, JobHunterCampaign
from app.core.config import settings

class ScraperService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def build_url_hash(self, user_id: str, company: str, title: str, apply_url: str) -> str:
        raw = f"{user_id}|{company.lower().strip()}|{title.lower().strip()}|{apply_url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def passes_remote_filter(self, job: dict, user_country: str) -> bool:
        if job.get("remote"):
            return True
        loc_country = (job.get("location_country") or "").upper()
        if not loc_country:
            return False  # ambiguous → skip
        return loc_country == user_country.upper()

    async def _call_haiku(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    async def score_job_match(self, title: str, description: str, sub_categories: list[str]) -> str:
        prompt = (
            f"Job title: {title}\nDescription (first 500 chars): {description[:500]}\n"
            f"Candidate sub-categories: {', '.join(sub_categories)}\n"
            f"Does this job's CORE requirement match the candidate's specialties? "
            f"Reply with exactly one word: MATCH, PARTIAL, or SKIP."
        )
        result = await self._call_haiku(prompt)
        for word in ["MATCH", "PARTIAL", "SKIP"]:
            if word in result.upper():
                return word
        return "SKIP"

    async def save_listing(self, campaign_id: str, user_id: str, job: dict, score: str) -> JobListing | None:
        url_hash = self.build_url_hash(user_id, job.get("company", ""), job.get("title", ""), job.get("apply_url") or job.get("url", ""))
        listing = JobListing(
            id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            source=job.get("source", "unknown"),
            title=job.get("title", ""),
            company=job.get("company", ""),
            location=job.get("location"),
            location_country=job.get("location_country"),
            remote=job.get("remote", False),
            url=job.get("url", ""),
            apply_url=job.get("apply_url"),
            description=job.get("description", "")[:5000],
            match_score=score,
            sub_category=job.get("sub_category"),
            url_hash=url_hash,
            status="pending" if score != "SKIP" else "skipped",
        )
        self.db.add(listing)
        try:
            await self.db.commit()
            return listing
        except IntegrityError:
            await self.db.rollback()
            return None  # duplicate — silently dropped

    async def run_jobspy(self, campaign: JobHunterCampaign) -> list[dict]:
        """Scrape jobs from multiple sources via JobSpy."""
        import asyncio
        from jobspy import scrape_jobs
        results = await asyncio.to_thread(
            scrape_jobs,
            site_name=["google", "indeed", "glassdoor", "zip_recruiter"],
            search_term=campaign.broad_category,
            results_wanted=50,
            hours_old=24,
        )
        jobs = []
        for _, row in results.iterrows():
            is_remote = str(row.get("is_remote", "")).lower() == "true"
            # skip LinkedIn Easy Apply
            apply_url = str(row.get("job_url_direct") or row.get("job_url") or "")
            if "linkedin.com/jobs/apply" in apply_url:
                continue
            jobs.append({
                "source": "jobspy",
                "title": str(row.get("title", "")),
                "company": str(row.get("company", "")),
                "location": str(row.get("location", "")),
                "location_country": str(row.get("country") or "")[:2].upper() or None,
                "remote": is_remote,
                "url": str(row.get("job_url", "")),
                "apply_url": apply_url,
                "description": str(row.get("description") or ""),
            })
        return jobs

    async def scrape_campaign(self, campaign_id: str, user_id: str) -> int:
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one()
        raw_jobs = await self.run_jobspy(campaign)
        saved = 0
        for job in raw_jobs:
            if not self.passes_remote_filter(job, campaign.user_country or ""):
                continue
            score = await self.score_job_match(job["title"], job["description"], campaign.sub_categories)
            listing = await self.save_listing(campaign_id, user_id, job, score)
            if listing:
                saved += 1
        return saved
```

- [ ] **Step 4: Create scraper_worker.py**

```python
# backend/app/workers/scraper_worker.py
import asyncio
from app.core.celery_app import celery_app

@celery_app.task(name="app.workers.scraper_worker.scrape_campaign")
def scrape_campaign(campaign_id: str, user_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.scraper_service import ScraperService
    async def _run():
        async with AsyncSessionLocal() as db:
            service = ScraperService(db)
            count = await service.scrape_campaign(campaign_id, user_id)
            return {"scraped": count}
    return asyncio.run(_run())

@celery_app.task(name="app.workers.scraper_worker.scrape_all_active_campaigns")
def scrape_all_active_campaigns() -> None:
    import asyncio
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.pg.job_hunter import JobHunterCampaign
    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(JobHunterCampaign).where(JobHunterCampaign.status == "active")
            )
            campaigns = result.scalars().all()
            for c in campaigns:
                scrape_campaign.delay(c.id, c.user_id)
    asyncio.run(_run())
```

- [ ] **Step 5: Run tests — expect pass**

```bash
cd backend && pytest tests/services/test_scraper_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/job_hunter/scraper_service.py \
        backend/app/workers/scraper_worker.py \
        backend/tests/services/test_scraper_service.py
git commit -m "feat(step-4): job discovery — JobSpy scraping, remote filter, dedup, Haiku scoring"
```

---

## Task 5: Resume Tailoring

**Files:**
- Create: `backend/app/services/job_hunter/tailor_service.py`
- Create: `backend/app/workers/tailor_worker.py`
- Create: `backend/tests/services/test_tailor_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_tailor_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.tailor_service import TailorService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db

async def test_extract_keywords_returns_list(mock_db):
    service = TailorService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='["Python", "Django", "REST API"]')):
        keywords = await service.extract_keywords("We need a Python Django developer...")
    assert isinstance(keywords, list)
    assert "Python" in keywords

async def test_rewrite_bullets_calls_haiku(mock_db):
    service = TailorService(mock_db)
    bullets = ["Built web apps", "Managed databases"]
    keywords = ["Django", "PostgreSQL"]
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='["Built Django web apps", "Managed PostgreSQL databases"]')):
        result = await service.rewrite_bullets(bullets, keywords)
    assert isinstance(result, list)
    assert len(result) == 2

async def test_infer_salary_returns_string(mock_db):
    service = TailorService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="$90,000 - $120,000")):
        salary = await service.infer_salary(seniority="mid", location="London", company="Startup")
    assert isinstance(salary, str)
    assert len(salary) > 0
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && pytest tests/services/test_tailor_service.py -v
```

- [ ] **Step 3: Implement tailor_service.py**

```python
# backend/app/services/job_hunter/tailor_service.py
import json, uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobListing, JobHunterProfile, Application
from app.core.config import settings

class TailorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_haiku(self, prompt: str, max_tokens: int = 1000) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    async def extract_keywords(self, jd: str) -> list[str]:
        raw = await self._call_haiku(
            f"Extract the 15 most important ATS keywords from this job description. Return a JSON array of strings only.\n\n{jd[:3000]}"
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        return json.loads(raw[start:end])

    async def rewrite_bullets(self, bullets: list[str], keywords: list[str]) -> list[str]:
        raw = await self._call_haiku(
            f"Rewrite these resume bullets to naturally include relevant keywords. "
            f"Never invent experience — only reformulate using JD vocabulary. "
            f"Keywords: {', '.join(keywords[:10])}. Bullets: {json.dumps(bullets)}. "
            f"Return a JSON array of rewritten bullet strings."
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        return json.loads(raw[start:end])

    async def infer_salary(self, seniority: str, location: str, company: str) -> str:
        return await self._call_haiku(
            f"What is a realistic salary range for a {seniority}-level developer in {location} at a {company}? "
            f"Return only the range as a string, e.g. '$90,000 - $120,000'.",
            max_tokens=50,
        )

    async def generate_summary(self, profile: dict, keywords: list[str], role: str) -> str:
        return await self._call_haiku(
            f"Write a 2-3 sentence professional summary for a {role} role. "
            f"Profile skills: {', '.join(profile.get('skills', [])[:10])}. "
            f"Inject these keywords naturally: {', '.join(keywords[:8])}. "
            f"Return only the summary text.",
            max_tokens=200,
        )

    async def tailor_for_listing(self, listing_id: str, user_id: str) -> Application | None:
        listing_result = await self.db.execute(select(JobListing).where(JobListing.id == listing_id))
        listing = listing_result.scalar_one_or_none()
        if not listing or not listing.description:
            return None

        profile_result = await self.db.execute(select(JobHunterProfile).where(JobHunterProfile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return None

        keywords = await self.extract_keywords(listing.description)
        experience = profile.work_experience or []
        all_bullets = [b for job in experience for b in (job.get("responsibilities", "").split("\n") if isinstance(job.get("responsibilities"), str) else [])]
        rewritten = await self.rewrite_bullets(all_bullets[:10], keywords) if all_bullets else []
        seniority = "mid"  # simple inference; can be improved
        salary = await self.infer_salary(seniority, listing.location or "remote", listing.company)
        summary = await self.generate_summary(profile.__dict__, keywords, listing.title)
        cover_letter = await self._call_haiku(
            f"Write a concise cover letter for {listing.title} at {listing.company}. "
            f"Profile: {', '.join(profile.skills[:8])}. Salary expectation: {salary}. "
            f"Keywords: {', '.join(keywords[:8])}. Return only the letter text.",
            max_tokens=400,
        )

        application = Application(
            id=str(uuid.uuid4()),
            campaign_id=listing.campaign_id,
            job_listing_id=listing.id,
            user_id=user_id,
            cover_letter=cover_letter,
            form_answers={"salary": salary, "summary": summary, "rewritten_bullets": rewritten},
            status="applied",
        )
        listing.status = "applying"
        self.db.add(application)
        await self.db.commit()
        return application
```

- [ ] **Step 4: Create tailor_worker.py**

```python
# backend/app/workers/tailor_worker.py
import asyncio
from app.core.celery_app import celery_app

@celery_app.task(name="app.workers.tailor_worker.tailor_listing")
def tailor_listing(listing_id: str, user_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.tailor_service import TailorService
    async def _run():
        async with AsyncSessionLocal() as db:
            service = TailorService(db)
            app = await service.tailor_for_listing(listing_id, user_id)
            return {"application_id": app.id if app else None}
    return asyncio.run(_run())
```

- [ ] **Step 5: Run tests — expect pass**

```bash
cd backend && pytest tests/services/test_tailor_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/job_hunter/tailor_service.py \
        backend/app/workers/tailor_worker.py \
        backend/tests/services/test_tailor_service.py
git commit -m "feat(step-5): resume tailoring — keyword extraction, bullet rewriting, cover letter, salary inference"
```

---

## Task 6: Auto-Apply Engine

**Files:**
- Create: `backend/app/services/job_hunter/apply_service.py`
- Create: `backend/app/workers/apply_worker.py`
- Create: `backend/tests/services/test_apply_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_apply_service.py
import pytest
from app.services.job_hunter.apply_service import ApplyService

def test_detect_ats_greenhouse():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://boards.greenhouse.io/stripe/jobs/123") == "greenhouse"

def test_detect_ats_lever():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://jobs.lever.co/openai/abc") == "lever"

def test_detect_ats_ashby():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://jobs.ashbyhq.com/anthropic/123") == "ashby"

def test_detect_ats_unknown():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://careers.somecompany.com/apply") == "generic"

def test_skip_linkedin_easy_apply():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://www.linkedin.com/jobs/apply/123") == "skip"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && pytest tests/services/test_apply_service.py -v
```

- [ ] **Step 3: Implement apply_service.py**

```python
# backend/app/services/job_hunter/apply_service.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import Application, JobListing
from app.core.config import settings

ATS_PATTERNS = {
    "greenhouse": ["boards.greenhouse.io", "grnh.se"],
    "lever": ["jobs.lever.co", "lever.co"],
    "ashby": ["jobs.ashbyhq.com", "ashbyhq.com"],
    "workday": ["myworkdayjobs.com", "workday.com"],
    "skip": ["linkedin.com/jobs/apply"],
}

class ApplyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def detect_ats(self, url: str) -> str:
        url_lower = url.lower()
        for ats, patterns in ATS_PATTERNS.items():
            if any(p in url_lower for p in patterns):
                return ats
        return "generic"

    async def submit_application(self, application_id: str) -> bool:
        result = await self.db.execute(select(Application).where(Application.id == application_id))
        application = result.scalar_one_or_none()
        if not application:
            return False

        listing_result = await self.db.execute(select(JobListing).where(JobListing.id == application.job_listing_id))
        listing = listing_result.scalar_one_or_none()
        if not listing or not listing.apply_url:
            application.status = "failed"
            await self.db.commit()
            return False

        ats = self.detect_ats(listing.apply_url)
        if ats == "skip":
            application.status = "failed"
            await self.db.commit()
            return False

        try:
            success = await asyncio.to_thread(
                self._fill_form_sync,
                listing.apply_url, ats, application.form_answers or {},
                application.cover_letter or "",
            )
            application.status = "applied" if success else "failed"
            listing.status = "applied" if success else "failed"
        except Exception as e:
            application.status = "failed"
            listing.status = "failed"
        await self.db.commit()
        return application.status == "applied"

    def _fill_form_sync(self, apply_url: str, ats: str, form_answers: dict, cover_letter: str) -> bool:
        """Playwright form filling — runs in thread via asyncio.to_thread."""
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            try:
                page.goto(apply_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
                # Fill common fields present across most ATS
                for selector, value in [
                    ('input[name*="name"], input[placeholder*="name"]', form_answers.get("full_name", "")),
                    ('input[name*="email"], input[type="email"]', form_answers.get("email", "")),
                    ('input[name*="phone"], input[type="tel"]', form_answers.get("phone", "")),
                    ('input[name*="linkedin"]', form_answers.get("linkedin_url", "")),
                    ('input[name*="github"]', form_answers.get("github_url", "")),
                    ('textarea[name*="cover"], textarea[placeholder*="cover"]', cover_letter),
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=2000):
                            el.fill(value)
                    except Exception:
                        pass
                # Submit
                submit = page.locator('button[type="submit"], input[type="submit"]').first
                if submit.is_visible(timeout=3000):
                    submit.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                return True
            except Exception:
                return False
            finally:
                browser.close()
```

- [ ] **Step 4: Create apply_worker.py**

```python
# backend/app/workers/apply_worker.py
import asyncio
from app.core.celery_app import celery_app

@celery_app.task(name="app.workers.apply_worker.submit_application")
def submit_application(application_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.apply_service import ApplyService
    async def _run():
        async with AsyncSessionLocal() as db:
            service = ApplyService(db)
            success = await service.submit_application(application_id)
            return {"success": success}
    return asyncio.run(_run())
```

- [ ] **Step 5: Run tests — expect pass**

```bash
cd backend && pytest tests/services/test_apply_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/job_hunter/apply_service.py \
        backend/app/workers/apply_worker.py \
        backend/tests/services/test_apply_service.py
git commit -m "feat(step-6): auto-apply — ATS detection, Playwright form filling, failure handling"
```

---

## Task 7: Email Intelligence

**Files:**
- Create: `backend/app/services/job_hunter/email_service.py`
- Create: `backend/app/workers/email_worker.py`
- Create: `backend/tests/services/test_email_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_email_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.email_service import EmailService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

async def test_classify_interview(mock_db):
    service = EmailService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="interview")):
        result = await service.classify_email("Interview Invitation - Software Engineer", "We'd like to invite you...")
    assert result == "interview"

async def test_classify_rejection(mock_db):
    service = EmailService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="rejection")):
        result = await service.classify_email("Update on your application", "We regret to inform you...")
    assert result == "rejection"

async def test_decrypt_credentials_roundtrip(mock_db):
    service = EmailService(mock_db)
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    with patch("app.services.job_hunter.email_service.settings") as mock_settings:
        mock_settings.job_hunter_encryption_key = key.decode()
        encrypted = service.encrypt_credentials({"host": "imap.gmail.com", "password": "secret"})
        decrypted = service.decrypt_credentials(encrypted)
    assert decrypted["password"] == "secret"

async def test_generate_rejection_reply_is_professional(mock_db):
    service = EmailService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="Thank you for your consideration...")):
        reply = await service.generate_rejection_reply("Google", "Software Engineer")
    assert isinstance(reply, str)
    assert len(reply) > 20
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && pytest tests/services/test_email_service.py -v
```

- [ ] **Step 3: Implement email_service.py**

```python
# backend/app/services/job_hunter/email_service.py
import imaplib, smtplib, email, uuid, json
from email.mime.text import MIMEText
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import EmailEvent, Application, JobHunterCampaign
from app.core.config import settings

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class EmailService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _fernet(self) -> Fernet:
        return Fernet(settings.job_hunter_encryption_key.encode())

    def encrypt_credentials(self, creds: dict) -> str:
        return self._fernet().encrypt(json.dumps(creds).encode()).decode()

    def decrypt_credentials(self, encrypted: str) -> dict:
        return json.loads(self._fernet().decrypt(encrypted.encode()).decode())

    async def _call_haiku(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip().lower()

    async def classify_email(self, subject: str, snippet: str) -> str:
        result = await self._call_haiku(
            f"Classify this email as exactly one word: interview, rejection, or other.\n"
            f"Subject: {subject}\nSnippet: {snippet[:300]}"
        )
        for label in ["interview", "rejection"]:
            if label in result:
                return label
        return "other"

    async def generate_rejection_reply(self, company: str, role: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content":
                f"Write a brief, professional reply to a rejection email from {company} for the {role} role. "
                f"Thank them, ask for specific feedback on what would make a stronger candidate in the future. "
                f"Tone: gracious, curious, forward-looking. Return only the email body."}],
        )
        return msg.content[0].text

    def fetch_new_emails(self, creds: dict, since: datetime) -> list[dict]:
        """Fetch emails received after `since` via IMAP."""
        try:
            mail = imaplib.IMAP4_SSL(creds["host"], creds.get("port", 993))
            mail.login(creds["username"], creds["password"])
            mail.select("INBOX")
            since_str = since.strftime("%d-%b-%Y")
            _, data = mail.search(None, f'(SINCE "{since_str}")')
            emails = []
            for num in (data[0].split() if data[0] else [])[:50]:  # max 50 per poll
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")[:500]
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")[:500]
                emails.append({
                    "subject": str(msg["Subject"] or ""),
                    "sender": str(msg["From"] or ""),
                    "date": str(msg["Date"] or ""),
                    "snippet": body,
                })
            mail.logout()
            return emails
        except Exception:
            return []

    def send_reply(self, creds: dict, to: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEText(body)
            msg["Subject"] = f"Re: {subject}"
            msg["From"] = creds["username"]
            msg["To"] = to
            with smtplib.SMTP_SSL(creds.get("smtp_host", creds["host"]), creds.get("smtp_port", 465)) as server:
                server.login(creds["username"], creds["password"])
                server.sendmail(creds["username"], [to], msg.as_string())
            return True
        except Exception:
            return False

    async def process_campaign_emails(self, campaign_id: str) -> None:
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign or not campaign.email_account_encrypted:
            return
        creds = self.decrypt_credentials(campaign.email_account_encrypted)
        since = campaign.email_monitor_since or _utcnow()
        import asyncio
        raw_emails = await asyncio.to_thread(self.fetch_new_emails, creds, since)
        for raw in raw_emails:
            email_type = await self.classify_email(raw["subject"], raw["snippet"])
            if email_type == "other":
                continue
            event = EmailEvent(
                id=str(uuid.uuid4()),
                campaign_id=campaign_id,
                type=email_type,
                subject=raw["subject"],
                sender=raw["sender"],
                received_at=_utcnow(),
                raw_snippet=raw["snippet"],
            )
            self.db.add(event)
            await self.db.commit()
            if email_type == "rejection":
                reply_body = await self.generate_rejection_reply(raw["sender"], raw["subject"])
                sent = await asyncio.to_thread(self.send_reply, creds, raw["sender"], raw["subject"], reply_body)
                if sent:
                    event.ai_reply_sent = True
                    event.ai_reply_body = reply_body
                    event.ai_reply_sent_at = _utcnow()
                    await self.db.commit()
            # Publish activity to Redis pub/sub
            from app.core.cache import get_redis
            r = await get_redis()
            await r.publish(f"campaign:{campaign_id}:activity", f"Email detected: {email_type} from {raw['sender']}")
```

- [ ] **Step 4: Create email_worker.py**

```python
# backend/app/workers/email_worker.py
import asyncio
from app.core.celery_app import celery_app

@celery_app.task(name="app.workers.email_worker.poll_all_campaigns")
def poll_all_campaigns() -> None:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService
    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(JobHunterCampaign).where(
                    JobHunterCampaign.status == "active",
                    JobHunterCampaign.email_account_encrypted.isnot(None),
                )
            )
            campaigns = result.scalars().all()
            for c in campaigns:
                service = EmailService(db)
                await service.process_campaign_emails(c.id)
    asyncio.run(_run())
```

- [ ] **Step 5: Run tests — expect pass**

```bash
cd backend && pytest tests/services/test_email_service.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/job_hunter/email_service.py \
        backend/app/workers/email_worker.py \
        backend/tests/services/test_email_service.py
git commit -m "feat(step-7): email intelligence — IMAP poll, classification, rejection replies, Redis pub/sub"
```

---

## Task 8: Calendar Sync

**Files:**
- Create: `backend/app/services/job_hunter/calendar_service.py`
- Create: `backend/tests/services/test_calendar_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_calendar_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.services.job_hunter.calendar_service import CalendarService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

async def test_extract_datetime_from_text(mock_db):
    service = CalendarService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='{"date": "2026-04-20", "time": "14:00", "duration_minutes": 60}')):
        result = await service.extract_interview_datetime("We'd like to meet on April 20th at 2pm for 1 hour")
    assert result["date"] == "2026-04-20"
    assert result["time"] == "14:00"

async def test_create_event_stores_in_db(mock_db):
    service = CalendarService(mock_db)
    mock_db.execute = AsyncMock()
    with patch.object(service, "_push_caldav_event", new=AsyncMock(return_value="ext-id-123")):
        await service.create_interview_event(
            application_id="app-1", email_event_id="email-1",
            company="Stripe", role="Engineer",
            scheduled_at=datetime(2026, 4, 20, 14, 0),
            duration_minutes=60, caldav_creds={"url": "https://caldav.example.com"}
        )
    mock_db.add.assert_called_once()
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && pytest tests/services/test_calendar_service.py -v
```

- [ ] **Step 3: Implement calendar_service.py**

```python
# backend/app/services/job_hunter/calendar_service.py
import uuid, json
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import CalendarEvent
from app.core.config import settings

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_haiku(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    async def extract_interview_datetime(self, email_body: str) -> dict:
        raw = await self._call_haiku(
            f"Extract interview date/time from this email. Return JSON: {{\"date\": \"YYYY-MM-DD\", \"time\": \"HH:MM\", \"duration_minutes\": N}}. "
            f"If unknown, use duration_minutes: 60.\nEmail: {email_body[:1000]}"
        )
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end])

    async def _push_caldav_event(self, creds: dict, title: str, scheduled_at: datetime, duration_minutes: int) -> str | None:
        try:
            import asyncio
            import caldav
            def _push():
                client = caldav.DAVClient(url=creds["url"], username=creds.get("username"), password=creds.get("password"))
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
            return None

    async def create_interview_event(
        self, application_id: str, email_event_id: str,
        company: str, role: str, scheduled_at: datetime,
        duration_minutes: int, caldav_creds: dict,
    ) -> CalendarEvent:
        title = f"Interview: {role} at {company}"
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
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd backend && pytest tests/services/test_calendar_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/job_hunter/calendar_service.py \
        backend/tests/services/test_calendar_service.py
git commit -m "feat(step-8): calendar sync — CalDAV integration, interview event creation"
```

---

## Task 9: Dashboard + WebSocket Activity Feed

**Files:**
- Create: `backend/app/services/job_hunter/dashboard_service.py`
- Create: `backend/app/api/v1/job_hunter/applications.py`
- Create: `backend/app/api/v1/job_hunter/ws.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement dashboard_service.py**

```python
# backend/app/services/job_hunter/dashboard_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.job_hunter import Application, EmailEvent, CalendarEvent, JobHunterCampaign, JobListing

class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_campaign_summary(self, campaign_id: str) -> dict:
        total = await self.db.execute(
            select(func.count()).where(Application.campaign_id == campaign_id)
        )
        interviews = await self.db.execute(
            select(func.count()).where(Application.campaign_id == campaign_id, Application.status == "interview")
        )
        rejections = await self.db.execute(
            select(func.count()).where(Application.campaign_id == campaign_id, Application.status == "rejected")
        )
        offers = await self.db.execute(
            select(func.count()).where(Application.campaign_id == campaign_id, Application.status == "offer")
        )
        return {
            "total_applications": total.scalar(),
            "interviews": interviews.scalar(),
            "rejections": rejections.scalar(),
            "offers": offers.scalar(),
        }

    async def get_pipeline(self, campaign_id: str) -> list[dict]:
        result = await self.db.execute(
            select(Application, JobListing)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.campaign_id == campaign_id)
            .order_by(Application.applied_at.desc())
            .limit(100)
        )
        rows = result.all()
        return [
            {
                "application_id": app.id,
                "status": app.status,
                "applied_at": app.applied_at.isoformat(),
                "company": listing.company,
                "title": listing.title,
                "location": listing.location,
                "match_score": listing.match_score,
                "cover_letter": app.cover_letter,
            }
            for app, listing in rows
        ]

    async def get_scheduled_interviews(self, campaign_id: str) -> list[dict]:
        result = await self.db.execute(
            select(CalendarEvent, Application, JobListing)
            .join(Application, CalendarEvent.application_id == Application.id)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.campaign_id == campaign_id)
            .order_by(CalendarEvent.scheduled_at)
        )
        return [
            {
                "calendar_event_id": ce.id,
                "application_id": app.id,
                "title": ce.title,
                "scheduled_at": ce.scheduled_at.isoformat(),
                "duration_minutes": ce.duration_minutes,
                "company": listing.company,
                "role": listing.title,
            }
            for ce, app, listing in result.all()
        ]
```

- [ ] **Step 2: Create dashboard + applications API**

```python
# backend/app/api/v1/job_hunter/applications.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.services.job_hunter.dashboard_service import DashboardService

router = APIRouter(prefix="/job-hunter/campaigns", tags=["job-hunter-dashboard"])

@router.get("/{campaign_id}/dashboard", response_model=dict)
async def get_dashboard(campaign_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    service = DashboardService(db)
    summary = await service.get_campaign_summary(campaign_id)
    pipeline = await service.get_pipeline(campaign_id)
    interviews = await service.get_scheduled_interviews(campaign_id)
    return {"data": {"summary": summary, "pipeline": pipeline, "interviews": interviews}, "error": None}
```

- [ ] **Step 3: Create WebSocket activity feed**

```python
# backend/app/api/v1/job_hunter/ws.py
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.cache import get_redis

router = APIRouter(tags=["job-hunter-ws"])

@router.websocket("/ws/campaign/{campaign_id}/activity")
async def campaign_activity_feed(websocket: WebSocket, campaign_id: str):
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"campaign:{campaign_id}:activity")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode())
    except WebSocketDisconnect:
        await pubsub.unsubscribe(f"campaign:{campaign_id}:activity")
```

- [ ] **Step 4: Register routers in main.py**

```python
from app.api.v1.job_hunter.applications import router as jh_applications_router
from app.api.v1.job_hunter.ws import router as jh_ws_router
app.include_router(jh_applications_router, prefix="/api/v1")
app.include_router(jh_ws_router, prefix="/api/v1")
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/job_hunter/dashboard_service.py \
        backend/app/api/v1/job_hunter/applications.py \
        backend/app/api/v1/job_hunter/ws.py \
        backend/app/main.py
git commit -m "feat(step-9): dashboard — pipeline view, summary stats, real-time activity WebSocket"
```

---

## Task 10: Interview Prep Bridge

**Files:**
- Modify: `backend/app/services/persona_engine.py`
- Create: `backend/app/services/job_hunter/bridge_service.py`
- Create: `backend/tests/services/test_bridge_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/test_bridge_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.bridge_service import BridgeService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    return db

async def test_get_interview_context_returns_structured_dict(mock_db):
    service = BridgeService(mock_db)
    mock_listing = MagicMock(company="Stripe", title="Backend Engineer")
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_listing)
    with patch("app.services.job_hunter.bridge_service.PersonaEngine") as MockEngine:
        mock_engine = MockEngine.return_value
        mock_engine.get_context = AsyncMock(return_value={
            "managers": [{"name": "John", "title": "VP Eng", "traits": ["direct"]}],
            "round_patterns": {"rounds": ["HR", "Technical"]},
            "persona_string": "John is direct and values clarity.",
        })
        result = await service.get_interview_context("app-1")
    assert "managers" in result
    assert "persona_string" in result
    assert result["company"] == "Stripe"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && pytest tests/services/test_bridge_service.py -v
```

- [ ] **Step 3: Add `_assemble_context` and `get_context` to PersonaEngine**

```python
# In backend/app/services/persona_engine.py — add after get_graph_context():

async def _assemble_context(self, company: str, role: str, round_type: str) -> dict:
    """Shared helper: fetch graph data and return structured context dict."""
    managers = await get_managers_for_company(company)
    round_ctx = await get_round_context(company, round_type)
    enriched_managers = []
    for m in managers:
        history = await get_manager_history(m["name"])
        previous = [h for h in history if h["relationship"] == "PREVIOUSLY_AT"]
        enriched_managers.append({**m, "previous_companies": [h["company"] for h in previous]})
    return {"managers": enriched_managers, "round_patterns": round_ctx}

async def build(self, company: str, role: str, round_type: str) -> str:
    # Refactored to use _assemble_context — return type unchanged
    manager_context = await self._assemble_context(company, role, round_type)
    return await self._orchestrator.build_persona(
        company=company, role=role, manager_context=manager_context,
    )

async def get_context(self, company: str, role: str, round_type: str = "HR") -> dict:
    """Return structured context dict + persona string for the Interview Prep bridge."""
    manager_context = await self._assemble_context(company, role, round_type)
    persona_string = await self._orchestrator.build_persona(
        company=company, role=role, manager_context=manager_context,
    )
    return {**manager_context, "persona_string": persona_string}
```

- [ ] **Step 4: Implement bridge_service.py**

```python
# backend/app/services/job_hunter/bridge_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import Application, JobListing
from app.services.persona_engine import PersonaEngine

class BridgeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._persona_engine = PersonaEngine()

    async def get_interview_context(self, application_id: str) -> dict:
        result = await self.db.execute(
            select(Application, JobListing)
            .join(JobListing, Application.job_listing_id == JobListing.id)
            .where(Application.id == application_id)
        )
        row = result.first()
        if not row:
            return {}
        application, listing = row
        context = await self._persona_engine.get_context(
            company=listing.company,
            role=listing.title,
            round_type="HR",
        )
        return {**context, "company": listing.company, "role": listing.title, "application_id": application_id}
```

- [ ] **Step 5: Add bridge API endpoint**

```python
# Add to backend/app/api/v1/job_hunter/applications.py:
from app.services.job_hunter.bridge_service import BridgeService

@router.get("/{campaign_id}/applications/{application_id}/interview-context", response_model=dict)
async def get_interview_context(
    campaign_id: str, application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = BridgeService(db)
    context = await service.get_interview_context(application_id)
    return {"data": context, "error": None}
```

- [ ] **Step 6: Run all tests**

```bash
cd backend && pytest tests/services/ tests/api/ -v --tb=short
```

Expected: all green. Fix any failures before proceeding.

- [ ] **Step 7: Run full test suite with coverage**

```bash
cd backend && pytest --cov=app/services/job_hunter --cov-report=term-missing -v
```

Expected: ≥ 80% coverage on all job_hunter services.

- [ ] **Step 8: Final commit**

```bash
git add backend/app/services/persona_engine.py \
        backend/app/services/job_hunter/bridge_service.py \
        backend/tests/services/test_bridge_service.py \
        backend/app/api/v1/job_hunter/applications.py
git commit -m "feat(step-10): interview prep bridge — PersonaEngine.get_context(), bridge_service, API endpoint"
```

---

## Running the Full Stack

After all tasks complete:

```bash
# Start Redis
docker compose up redis -d

# Run DB migrations
cd backend && alembic upgrade head

# Start FastAPI
uvicorn app.main:app --reload --port 8000

# Start Celery worker
celery -A app.core.celery_app worker --loglevel=info --concurrency=4

# Start Celery Beat scheduler
celery -A app.core.celery_app beat --loglevel=info
```

**Verify success gate (spec Section 13, Step 10):**
- Create a campaign → sub-categories inferred ✓
- Scraper worker runs → jobs stored in `job_listings` ✓
- Tailor worker runs → `applications` created with cover letter ✓
- Fake rejection email → AI reply sent within 5 min ✓
- "Start Interview Prep" endpoint → returns persona + manager data ✓
