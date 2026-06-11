# backend/app/api/v1/job_hunter/campaigns.py
import io
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.job_hunter.campaign_service import CampaignService
from app.schemas.job_hunter import (
    CampaignCreateRequest, CampaignStatusRequest,
    EmailCredentialsRequest, CalDAVCredentialsRequest, LinkedInCredentialsRequest,
    CampaignProfileUpsertRequest, RawContextRequest, ManualJobRequest,
)
from app.services.job_hunter.campaign_profile_service import JOB_CATEGORIES, WORK_TYPES

router = APIRouter(prefix="/job-hunter/campaigns", tags=["job-hunter-campaigns"])
bearer = HTTPBearer()

def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)

@router.get("/meta", response_model=dict)
async def get_campaign_meta(user_id: str = Depends(get_user_id)):
    """Returns available job categories and work types for the creation form."""
    return {"data": {"categories": JOB_CATEGORIES, "work_types": WORK_TYPES}, "error": None}


@router.post("", response_model=dict)
async def create_campaign(
    body: CampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    # Resolve categories — multi-select takes priority over legacy single-select
    effective_categories = body.categories if body.categories else (
        [body.broad_category] if body.broad_category else []
    )
    if not effective_categories:
        raise HTTPException(status_code=400, detail="Select at least one job category")
    invalid = [c for c in effective_categories if c not in JOB_CATEGORIES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid categories: {', '.join(invalid)}. Choose from: {', '.join(JOB_CATEGORIES)}")

    # Resolve work types — multi-select takes priority over legacy single-select
    effective_work_types = body.work_types if body.work_types else [body.work_type]

    if not body.anywhere and not body.user_country:
        raise HTTPException(status_code=400, detail="Provide user_country or set anywhere=true")

    service = CampaignService(db)
    campaign = await service.create_campaign(
        user_id=user_id,
        name=body.name,
        broad_category=effective_categories[0],
        sub_categories=effective_categories[1:],
        user_country=body.user_country,
        anywhere=body.anywhere,
        work_type=effective_work_types[0] if len(effective_work_types) == 1 else "any",
        work_types=effective_work_types if len(effective_work_types) > 1 else None,
        profile_overrides=body.profile_overrides,
    )
    return {"data": {
        "id": campaign.id, "name": campaign.name, "status": campaign.status,
        "broad_category": campaign.broad_category, "work_type": campaign.work_type,
        "work_types": campaign.work_types,
        "anywhere": campaign.anywhere, "user_country": campaign.user_country,
        "sub_categories": campaign.sub_categories,
    }, "error": None}

@router.get("/{campaign_id}/profile", response_model=dict)
async def get_campaign_profile(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    from app.services.job_hunter.campaign_profile_service import CampaignProfileService
    svc = CampaignProfileService(db)
    profile = await svc.get_or_create(campaign_id, user_id)
    return {"data": {
        "id": profile.id,
        "full_name": profile.full_name, "email": profile.email, "phone": profile.phone,
        "city": profile.city, "country": profile.country,
        "linkedin_url": profile.linkedin_url, "github_url": profile.github_url,
        "portfolio_url": profile.portfolio_url,
        "work_experience": profile.work_experience, "education": profile.education,
        "skills": profile.skills, "projects": profile.projects,
        "languages_spoken": profile.languages_spoken, "achievements": profile.achievements,
        "raw_context": profile.raw_context,
        "is_complete": profile.is_complete, "completion_gaps": profile.completion_gaps,
    }, "error": None}


@router.put("/{campaign_id}/profile", response_model=dict)
async def upsert_campaign_profile(
    campaign_id: str,
    body: CampaignProfileUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    from app.services.job_hunter.campaign_profile_service import CampaignProfileService
    from app.services.job_hunter.campaign_service import CampaignService
    svc = CampaignProfileService(db)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    profile = await svc.upsert(campaign_id, user_id, data)
    # Re-infer sub-categories if skills were updated
    if "skills" in data:
        await CampaignService(db).infer_sub_categories_from_profile(campaign_id)
    return {"data": {"updated": True, "is_complete": profile.is_complete}, "error": None}


@router.post("/{campaign_id}/profile/analyze", response_model=dict)
async def analyze_profile_gaps(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """AI reviews the profile and returns gaps, questions, and a readiness score."""
    from app.services.job_hunter.campaign_profile_service import CampaignProfileService
    svc = CampaignProfileService(db)
    result = await svc.analyze_gaps(campaign_id, user_id)
    return {"data": result, "error": None}


@router.post("/{campaign_id}/profile/context", response_model=dict)
async def process_raw_context(
    campaign_id: str,
    body: RawContextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Paste any raw text (old CV, LinkedIn bio, etc) — AI extracts and merges structured data."""
    from app.services.job_hunter.campaign_profile_service import CampaignProfileService
    svc = CampaignProfileService(db)
    result = await svc.process_raw_context(campaign_id, user_id, body.raw_context)
    return {"data": result, "error": None}


_ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md"}
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _clean_extracted_text(text: str) -> str:
    """
    Compress extracted text before sending to the LLM.
    Removes token-wasting noise without touching meaningful content.
    Falls back to a plain truncation if cleaning wipes everything (safety net).
    """
    import re

    original = text

    # Strip HTML tags that leak through from DOCX XML
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove actual base64 blobs: must end with = padding AND have no spaces —
    # real base64 is a solid block; normal English words never end in = or ==.
    text = re.sub(r"\b[A-Za-z0-9+/]{80,}={1,2}\b", "", text)

    # Collapse long runs of pure separator characters on their own line
    # (===== / ----- / _____ / ·····) — common in PDF/DOCX header borders
    text = re.sub(r"(?m)^[ \t]*[-=_·•█▪]{4,}[ \t]*$", "", text)

    # Remove bare page-number lines: a line that is just a number or "Page N of M"
    text = re.sub(r"(?m)^\s*(Page\s+\d+\s+of\s+\d+|\d{1,4})\s*$", "", text)

    # Collapse 3+ consecutive blank lines into one blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Normalise horizontal whitespace per line (tabs / multiple spaces → single space)
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines).strip()

    # Safety net: if cleaning removed everything, fall back to plain truncation
    if not text and original.strip():
        text = re.sub(r"\n{3,}", "\n\n", original).strip()

    # Hard cap — 12 000 chars ≈ 3 000 tokens; a resume has everything before this
    return text[:12_000]


@router.post("/{campaign_id}/profile/context/file", response_model=dict)
async def process_context_file(
    campaign_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Upload a PDF, DOCX, TXT, or MD file — text is extracted, cleaned, and fed to the profile AI pipeline."""
    import pdfplumber
    import docx as python_docx
    from app.services.job_hunter.campaign_profile_service import CampaignProfileService

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT, MD.")

    raw = await file.read()
    if len(raw) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum 5 MB.")

    if ext == ".pdf":
        text = ""
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        text = _clean_extracted_text(text)
    elif ext in (".docx", ".doc"):
        doc = python_docx.Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        text = _clean_extracted_text(text)
    else:
        # .txt and .md — already human-readable; just cap at 12 000 chars
        text = raw.decode("utf-8", errors="ignore").strip()[:12_000]

    if not text:
        raise HTTPException(status_code=422, detail="Could not extract text from the file.")

    svc = CampaignProfileService(db)
    result = await svc.process_raw_context(campaign_id, user_id, text)
    return {"data": result, "error": None}


@router.get("", response_model=dict)
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = CampaignService(db)
    campaigns = await service.list_campaigns(user_id)
    return {"data": [{"id": c.id, "name": c.name, "status": c.status,
                      "sub_categories": c.sub_categories, "broad_category": c.broad_category} for c in campaigns], "error": None}

@router.post("/{campaign_id}/scrape", response_model=dict)
async def trigger_scrape(
    campaign_id: str,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Trigger a parallel per-board scrape run via the Celery dispatcher.

    Optional body fields (all have sensible defaults from the campaign):
      company_types: list[str]  — ["startup","faang","enterprise","sme"] subset
      work_type:     str        — "remote"|"hybrid"|"onsite"|"any"
      regions:       list[str]  — ["kenya","africa","global"] subset; [] = anywhere
      daily_target:  int        — max MATCH listings to collect (default 100)
    """
    from sqlalchemy import select
    from app.models.pg.job_hunter import CampaignProfile, JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService
    from app.services.job_hunter.campaign_profile_service import CampaignProfileService

    body = body or {}

    # ── Profile guard ─────────────────────────────────────────────────────
    profile_result = await db.execute(
        select(CampaignProfile).where(CampaignProfile.campaign_id == campaign_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found. Fill in your profile before scraping.")

    missing = []
    if not (profile.full_name or "").strip():
        missing.append("full name")
    if not (profile.email or "").strip():
        missing.append("email")
    if not profile.skills and not (profile.raw_context or "").strip():
        missing.append("skills or profile context")
    if missing:
        raise HTTPException(status_code=400, detail=f"Profile incomplete: {', '.join(missing)}.")

    # ── Load campaign ─────────────────────────────────────────────────────
    campaign_result = await db.execute(
        select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    # ── Resolve LinkedIn credentials (if enabled) ─────────────────────────
    linkedin_creds: dict | None = None
    if campaign.linkedin_enabled:
        try:
            from app.models.pg.job_hunter import UserIntegration
            svc = EmailService(db)
            ui_result = await db.execute(select(UserIntegration).where(UserIntegration.user_id == user_id))
            ui = ui_result.scalar_one_or_none()
            encrypted = (ui.linkedin_account_encrypted if ui else None) or campaign.linkedin_account_encrypted
            if encrypted:
                linkedin_creds = svc.decrypt_credentials(encrypted)
        except Exception:
            pass

    # ── Build preferences ─────────────────────────────────────────────────
    # Resolve effective work types: body override > campaign.work_types > campaign.work_type
    if body.get("work_type"):
        effective_work_types = [body["work_type"]]
    elif campaign.work_types:
        effective_work_types = list(campaign.work_types)
    else:
        effective_work_types = [campaign.work_type or "any"]

    anywhere    = bool(campaign.anywhere)
    user_country = campaign.user_country or ""

    # Derive regions from location settings
    regions: list[str] = body.get("regions") or []
    if not regions and not anywhere:
        country_upper = user_country.upper()
        if country_upper == "KE":
            regions = ["kenya"]
        elif country_upper in ("NG", "GH", "ZA", "ET", "TZ", "UG", "RW"):
            regions = ["africa", "kenya"]
        # else: global (empty = all regions)

    preferences = {
        "search_term":    campaign.broad_category,
        "company_types":  body.get("company_types") or [],
        "work_type":      effective_work_types[0] if len(effective_work_types) == 1 else "any",
        "work_types":     effective_work_types,
        "regions":        regions,
        "user_country":   user_country,
        "anywhere":       anywhere,
        "daily_target":   int(body.get("daily_target") or 100),
        "max_rounds":     5,
        "sub_categories": list(campaign.sub_categories or []),
        "profile_skills": list(profile.skills or []),
        "linkedin_creds": linkedin_creds,
    }

    # ── Dispatch ──────────────────────────────────────────────────────────
    from app.workers.board_scrape_worker import dispatch_scrape
    dispatch_scrape.delay(
        campaign_id=campaign_id,
        user_id=user_id,
        preferences=preferences,
        dynamic_only=False,
        round_=1,
    )

    return {"data": {"started": True, "preferences": {k: v for k, v in preferences.items() if k != "linkedin_creds"}}, "error": None}


@router.post("/{campaign_id}/jobs/manual", response_model=dict)
async def add_manual_job(
    campaign_id: str,
    body: ManualJobRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Add a job manually to the campaign pipeline.
    Creates a JobListing (source='manual', match_score='MATCH') and queues tailoring.
    """
    import hashlib
    from app.models.pg.job_hunter import JobListing
    from sqlalchemy.exc import IntegrityError

    # Build a stable url_hash — use company+title since there's no real URL
    raw = f"{user_id}|{body.company.lower()}|{body.title.lower()}|manual"
    url_hash = hashlib.sha256(raw.encode()).hexdigest()

    # Synthetic URL so the unique constraint has something to key on
    synthetic_url = f"manual://{url_hash[:12]}"

    listing = JobListing(
        campaign_id=campaign_id,
        source="manual",
        title=body.title.strip(),
        company=body.company.strip(),
        location=body.location,
        remote=False,
        url=body.apply_url or synthetic_url,
        apply_url=body.apply_url,
        description=body.description.strip()[:10000],
        match_score="MATCH",
        url_hash=url_hash,
        status="pending",
    )
    db.add(listing)
    try:
        await db.commit()
        await db.refresh(listing)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This job is already in the campaign.")

    # Queue tailoring — same pipeline as scraped jobs
    try:
        from app.workers.tailor_worker import tailor_listing
        tailor_listing.apply_async(args=[listing.id, user_id], queue="tailor", priority=9)
    except Exception:
        pass  # tailoring is best-effort; listing is already saved

    return {"data": {"listing_id": listing.id, "status": "queued"}, "error": None}


@router.post("/{campaign_id}/listings/{listing_id}/ensure-application", response_model=dict)
async def ensure_application(
    campaign_id: str,
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Ensure an Application record exists for this listing.
    Creates one (and queues tailoring) if it doesn't exist yet.
    Returns the application_id.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from app.models.pg.job_hunter import Application, JobListing

    # Verify listing belongs to this campaign
    result = await db.execute(
        select(JobListing).where(JobListing.id == listing_id, JobListing.campaign_id == campaign_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    # Check if application already exists
    app_result = await db.execute(
        select(Application).where(
            Application.job_listing_id == listing_id,
            Application.user_id == user_id,
        )
    )
    app = app_result.scalar_one_or_none()

    if not app:
        import uuid as _uuid
        app = Application(
            id=str(_uuid.uuid4()),
            campaign_id=campaign_id,
            job_listing_id=listing_id,
            user_id=user_id,
            status="pending",
        )
        db.add(app)
        try:
            await db.commit()
            await db.refresh(app)
        except IntegrityError:
            await db.rollback()
            # Race condition — fetch the one that was just created
            app_result2 = await db.execute(
                select(Application).where(
                    Application.job_listing_id == listing_id,
                    Application.user_id == user_id,
                )
            )
            app = app_result2.scalar_one()

    return {"data": {"application_id": app.id}, "error": None}


@router.get("/{campaign_id}/scrape/status", response_model=dict)
async def get_scrape_status(
    campaign_id: str,
    user_id: str = Depends(get_user_id),
):
    """
    Returns per-board scrape status for the current run.

    Each board entry: {status: queued|running|done|failed, count: int, error: str|None}
    Also returns the overall run status.
    """
    from app.workers.board_scrape_worker import _get_all_board_statuses, _redis
    from app.services.job_hunter.board_registry import all_boards
    import json

    board_statuses = _get_all_board_statuses(campaign_id)

    # Overall run status
    run_status: dict = {}
    try:
        r = _redis()
        raw = r.get(f"scrape_run:{campaign_id}")
        if raw:
            run_status = json.loads(raw)
    except Exception:
        pass

    return {
        "data": {
            "run": run_status,
            "boards": board_statuses,
        },
        "error": None,
    }


@router.post("/{campaign_id}/scrape/stop", response_model=dict)
async def stop_scrape(
    campaign_id: str,
    user_id: str = Depends(get_user_id),
):
    """
    Stop an in-progress scrape by revoking all queued/running Celery tasks
    and marking the run as done.
    """
    import json
    from app.workers.board_scrape_worker import _redis, _set_run_status
    from app.core.celery_app import celery_app

    revoked = 0
    try:
        r = _redis()
        raw = r.get(f"scrape_tasks:{campaign_id}")
        if raw:
            task_ids = json.loads(raw)
            for task_id in task_ids:
                celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
                revoked += 1
            r.delete(f"scrape_tasks:{campaign_id}")
    except Exception:
        pass

    _set_run_status(campaign_id, "done")

    return {"data": {"stopped": True, "revoked": revoked}, "error": None}


@router.put("/{campaign_id}/credentials/email", response_model=dict)
async def set_email_credentials(
    campaign_id: str,
    body: EmailCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Store IMAP/SMTP credentials (Fernet-encrypted) for email monitoring."""
    from sqlalchemy import select
    from datetime import datetime, timezone
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService
    result = await db.execute(
        select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id, JobHunterCampaign.user_id == user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    creds = body.model_dump()
    if not creds.get("smtp_host"):
        creds["smtp_host"] = creds["host"]
    svc = EmailService(db)
    campaign.email_account_encrypted = svc.encrypt_credentials(creds)
    campaign.email_monitor_since = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return {"data": {"configured": True}, "error": None}


@router.put("/{campaign_id}/credentials/caldav", response_model=dict)
async def set_caldav_credentials(
    campaign_id: str,
    body: CalDAVCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Store CalDAV credentials (Fernet-encrypted) for calendar sync."""
    from sqlalchemy import select
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService
    result = await db.execute(
        select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id, JobHunterCampaign.user_id == user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    svc = EmailService(db)
    campaign.caldav_account_encrypted = svc.encrypt_credentials(body.model_dump())
    await db.commit()
    return {"data": {"configured": True}, "error": None}


@router.get("/{campaign_id}/credentials/status", response_model=dict)
async def get_credentials_status(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Returns which integrations are configured (without exposing credentials)."""
    from sqlalchemy import select
    from app.models.pg.job_hunter import JobHunterCampaign
    result = await db.execute(
        select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id, JobHunterCampaign.user_id == user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"data": {
        "email_configured": bool(campaign.email_account_encrypted),
        "caldav_configured": bool(campaign.caldav_account_encrypted),
        "linkedin_configured": bool(campaign.linkedin_account_encrypted),
    }, "error": None}


@router.post("/{campaign_id}/credentials/email/test", response_model=dict)
async def test_email_credentials(
    campaign_id: str,
    body: EmailCredentialsRequest,
    user_id: str = Depends(get_user_id),
):
    """Test IMAP connection without saving credentials."""
    import asyncio, imaplib
    def _test():
        try:
            mail = imaplib.IMAP4_SSL(body.host, body.port)
            mail.login(body.username, body.password)
            mail.logout()
            return True, None
        except imaplib.IMAP4.error as e:
            return False, f"Authentication failed: {e}"
        except OSError as e:
            return False, f"Cannot reach {body.host}:{body.port} — {e}"
        except Exception as e:
            return False, str(e)
    ok, err = await asyncio.to_thread(_test)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"data": {"ok": True}, "error": None}


@router.post("/{campaign_id}/credentials/caldav/test", response_model=dict)
async def test_caldav_credentials(
    campaign_id: str,
    body: CalDAVCredentialsRequest,
    user_id: str = Depends(get_user_id),
):
    """Test CalDAV connection without saving credentials."""
    import asyncio
    def _test():
        try:
            import caldav
            client = caldav.DAVClient(url=body.url, username=body.username, password=body.password)
            principal = client.principal()
            calendars = principal.calendars()
            return True, f"Connected — {len(calendars)} calendar(s) found"
        except Exception as e:
            return False, str(e)
    ok, msg = await asyncio.to_thread(_test)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"data": {"ok": True, "message": msg}, "error": None}


@router.put("/{campaign_id}/credentials/linkedin", response_model=dict)
async def set_linkedin_credentials(
    campaign_id: str,
    body: LinkedInCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Store LinkedIn credentials (Fernet-encrypted) for job scraping and outreach."""
    from sqlalchemy import select
    from app.models.pg.job_hunter import JobHunterCampaign
    from app.services.job_hunter.email_service import EmailService
    result = await db.execute(
        select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id, JobHunterCampaign.user_id == user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    svc = EmailService(db)
    campaign.linkedin_account_encrypted = svc.encrypt_credentials(body.model_dump())
    await db.commit()
    return {"data": {"configured": True}, "error": None}


@router.post("/{campaign_id}/credentials/linkedin/test", response_model=dict)
async def test_linkedin_credentials(
    campaign_id: str,
    body: LinkedInCredentialsRequest,
    user_id: str = Depends(get_user_id),
):
    """Test LinkedIn auth without saving credentials. Supports email/password or session cookie."""
    from app.services.job_hunter.linkedin_scraper import LinkedInScraper
    from app.services.job_hunter.browser_service import BrowserService
    try:
        mode = body.mode()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    scraper = LinkedInScraper(
        email=body.email,
        password=body.password,
        session_cookie=body.session_cookie,
    )
    try:
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            if mode == "cookie":
                ok = await scraper._auth_via_cookie(browser, page)
            else:
                ok = await scraper._login(browser, page)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Browser error: {e}")
    if not ok:
        detail = (
            "Session cookie is invalid or expired — please get a fresh li_at cookie"
            if mode == "cookie"
            else "LinkedIn login failed — check email and password"
        )
        raise HTTPException(status_code=400, detail=detail)
    return {"data": {"ok": True, "mode": mode}, "error": None}


@router.delete("/{campaign_id}", response_model=dict)
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Soft-delete a campaign (sets deleted_at). Irreversible from the UI."""
    service = CampaignService(db)
    try:
        await service.delete_campaign(campaign_id, user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"data": {"deleted": True}, "error": None}


@router.patch("/{campaign_id}/toggles", response_model=dict)
async def set_campaign_toggles(
    campaign_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Enable/disable integrations for a specific campaign."""
    from sqlalchemy import select
    from app.models.pg.job_hunter import JobHunterCampaign
    result = await db.execute(
        select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id, JobHunterCampaign.user_id == user_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for field in ("email_enabled", "caldav_enabled", "linkedin_enabled"):
        if field in body:
            setattr(campaign, field, bool(body[field]))
    await db.commit()
    return {"data": {"updated": True}, "error": None}


@router.patch("/{campaign_id}/status", response_model=dict)
async def update_status(
    campaign_id: str,
    body: CampaignStatusRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = CampaignService(db)
    try:
        await service.set_status(campaign_id, user_id, body.status)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"data": {"updated": True}, "error": None}
