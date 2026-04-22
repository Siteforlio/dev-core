# backend/app/api/v1/job_hunter/campaigns.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.job_hunter.campaign_service import CampaignService
from app.schemas.job_hunter import (
    CampaignCreateRequest, CampaignStatusRequest,
    EmailCredentialsRequest, CalDAVCredentialsRequest, LinkedInCredentialsRequest,
    CampaignProfileUpsertRequest, RawContextRequest,
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
    if body.broad_category not in JOB_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Choose from: {', '.join(JOB_CATEGORIES)}")
    if not body.anywhere and not body.user_country:
        raise HTTPException(status_code=400, detail="Provide user_country or set anywhere=true")
    service = CampaignService(db)
    campaign = await service.create_campaign(
        user_id=user_id,
        name=body.name,
        broad_category=body.broad_category,
        user_country=body.user_country,
        anywhere=body.anywhere,
        work_type=body.work_type,
        profile_overrides=body.profile_overrides,
    )
    return {"data": {
        "id": campaign.id, "name": campaign.name, "status": campaign.status,
        "broad_category": campaign.broad_category, "work_type": campaign.work_type,
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
    if not profile.skills:
        missing.append("skills")
    if not profile.work_experience:
        missing.append("work experience")
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
    work_type   = body.get("work_type") or campaign.work_type or "any"
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
        "work_type":      work_type,
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
