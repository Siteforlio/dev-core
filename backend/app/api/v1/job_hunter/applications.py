from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.models.pg.job_hunter import Application, JobListing, JobHunterCampaign
from app.services.job_hunter.dashboard_service import DashboardService
from app.services.job_hunter.bridge_service import BridgeService
from app.services.job_hunter.apply_chat_service import ApplyChatService

router = APIRouter(prefix="/job-hunter/campaigns", tags=["job-hunter-dashboard"])
bearer = HTTPBearer()


def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/{campaign_id}/dashboard", response_model=dict)
async def get_dashboard(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = DashboardService(db)
    summary = await service.get_campaign_summary(campaign_id, user_id)
    pipeline = await service.get_pipeline(campaign_id, user_id)
    interviews = await service.get_scheduled_interviews(campaign_id, user_id)
    activity_log = await service.get_activity_log(campaign_id, user_id)
    return {"data": {"summary": summary, "pipeline": pipeline, "interviews": interviews, "activity_log": activity_log}, "error": None}


# ── Interview prep ────────────────────────────────────────────────────────────

@router.get("/{campaign_id}/applications/{application_id}/interview-context", response_model=dict)
async def get_interview_context(
    campaign_id: str,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = BridgeService(db)
    context = await service.get_interview_context(application_id, campaign_id=campaign_id)
    return {"data": context, "error": None}


# ── Apply panel: application detail ──────────────────────────────────────────

@router.get("/{campaign_id}/applications/{application_id}/detail", response_model=dict)
async def get_application_detail(
    campaign_id: str,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Returns everything the apply panel needs:
    - resume path + folder + filename
    - cover letter
    - apply URL
    - job title / company
    - email tracking status
    """
    result = await db.execute(
        select(Application, JobListing, JobHunterCampaign)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .join(JobHunterCampaign, Application.campaign_id == JobHunterCampaign.id)
        .where(
            Application.id == application_id,
            Application.campaign_id == campaign_id,
            Application.user_id == user_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app, listing, campaign = row

    from pathlib import Path
    pdf_path = Path(app.tailored_resume_pdf_url) if app.tailored_resume_pdf_url else None

    return {
        "data": {
            "application_id": app.id,
            "status": app.status,
            "company": listing.company,
            "title": listing.title,
            "location": listing.location,
            "apply_url": listing.apply_url or listing.url,
            "campaign_name": campaign.name,
            "resume_path": str(pdf_path) if pdf_path else None,
            "resume_folder": str(pdf_path.parent) if pdf_path else None,
            "resume_filename": pdf_path.name if pdf_path else None,
            "cover_letter": app.cover_letter,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
        },
        "error": None,
    }


# ── Apply panel: mark applied / update status ─────────────────────────────────

class StatusPatch(BaseModel):
    status: str  # applied | failed | withdrawn
    notes: str | None = None


@router.patch("/{campaign_id}/applications/{application_id}/status", response_model=dict)
async def patch_application_status(
    campaign_id: str,
    application_id: str,
    body: StatusPatch,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    allowed = {"applied", "failed", "withdrawn", "pending"}
    if body.status not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {allowed}")

    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.campaign_id == campaign_id,
            Application.user_id == user_id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    app.status = body.status
    app.status_updated_at = now
    if body.status == "applied":
        app.applied_at = now
    if body.notes:
        existing = app.form_answers or {}
        existing["apply_notes"] = body.notes
        app.form_answers = existing

    await db.commit()
    return {"data": {"status": app.status}, "error": None}


# ── Apply panel: generate / regenerate cover letter ──────────────────────────

@router.post("/{campaign_id}/applications/{application_id}/cover-letter", response_model=dict)
async def generate_cover_letter(
    campaign_id: str,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(
            Application.id == application_id,
            Application.campaign_id == campaign_id,
            Application.user_id == user_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app, listing = row
    svc = ApplyChatService(db)
    cover_letter = await svc.generate_cover_letter(app, listing)

    app.cover_letter = cover_letter
    from datetime import datetime, timezone
    app.status_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    return {"data": {"cover_letter": cover_letter}, "error": None}


# ── Apply panel: job-scoped AI chat ──────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@router.post("/{campaign_id}/applications/{application_id}/chat", response_model=dict)
async def apply_chat(
    campaign_id: str,
    application_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(
            Application.id == application_id,
            Application.campaign_id == campaign_id,
            Application.user_id == user_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app, listing = row
    svc = ApplyChatService(db)
    reply = await svc.chat(
        application=app,
        listing=listing,
        user_message=body.message,
        history=[{"role": m.role, "content": m.content} for m in body.history],
    )
    return {"data": {"reply": reply}, "error": None}


# ── Apply panel: open apply URL in Chrome ────────────────────────────────────

@router.post("/{campaign_id}/applications/{application_id}/open-in-chrome", response_model=dict)
async def open_in_chrome(
    campaign_id: str,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Open the job's apply URL in the system Chrome browser."""
    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(
            Application.id == application_id,
            Application.campaign_id == campaign_id,
            Application.user_id == user_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app, listing = row
    url = listing.apply_url or listing.url
    if not url:
        raise HTTPException(status_code=422, detail="No apply URL for this listing")

    import subprocess, shutil, sys
    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "google-chrome",
        "chromium",
    ]
    from pathlib import Path as _Path
    chrome = next(
        (c for c in chrome_candidates if shutil.which(c) or _Path(c).exists()),
        None,
    )
    if chrome:
        subprocess.Popen([chrome, url])
    else:
        # Fallback: system default browser
        import webbrowser
        webbrowser.open(url)

    return {"data": {"opened": True, "url": url}, "error": None}


# ── Apply panel: email tracking status ───────────────────────────────────────

@router.get("/{campaign_id}/applications/{application_id}/tracking", response_model=dict)
async def get_tracking_status(
    campaign_id: str,
    application_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Returns email monitoring status and any detected responses for this application."""
    from app.models.pg.job_hunter import EmailEvent
    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(
            Application.id == application_id,
            Application.campaign_id == campaign_id,
            Application.user_id == user_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app, listing = row

    # Fetch email events linked to this campaign (simple keyword match on company)
    events_result = await db.execute(
        select(EmailEvent)
        .where(EmailEvent.campaign_id == campaign_id)
        .order_by(EmailEvent.received_at.desc())
        .limit(20)
    )
    events = events_result.scalars().all()

    # Filter events relevant to this application by company name match
    company_lower = (listing.company or "").lower()
    relevant = [
        {
            "id": e.id,
            "subject": e.subject,
            "sender": e.sender,
            "classification": e.classification,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in events
        if company_lower and company_lower in (e.sender or "").lower()
    ]

    return {
        "data": {
            "application_id": app.id,
            "status": app.status,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
            "company": listing.company,
            "title": listing.title,
            "email_events": relevant,
        },
        "error": None,
    }
