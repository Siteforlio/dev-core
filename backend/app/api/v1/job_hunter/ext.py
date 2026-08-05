"""
Extension API — endpoints called by the Chrome browser extension.
All auth via Bearer JWT. User-scoped only (no campaign_id in path).
"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.cache import cache_set, cache_get
from app.core.database import get_db
from app.core.security import decode_token, create_extension_token
from app.models.pg.job_hunter import Application, JobListing, JobHunterCampaign
from app.services.job_hunter.apply_chat_service import ApplyChatService

router = APIRouter(prefix="/job-hunter/ext", tags=["job-hunter-ext"])
bearer = HTTPBearer()

PENDING_FILL_TTL = 600  # 10 minutes


def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


def get_raw_token(credentials=Depends(bearer)) -> str:
    return credentials.credentials


async def _get_app_for_user(app_id: str, user_id: str, db: AsyncSession) -> tuple[Application, JobListing]:
    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(
            Application.id == app_id,
            Application.user_id == user_id,
            Application.deleted_at.is_(None),
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    return row.Application, row.JobListing


# ── POST /ext/token ───────────────────────────────────────────────────────────
# Called once by the dashboard when the user links the extension.
# Returns a 1-year JWT so the extension never needs to re-auth.

@router.post("/token", response_model=dict)
async def issue_extension_token(user_id: str = Depends(get_user_id)):
    ext_token = create_extension_token(user_id)
    return {"data": {"token": ext_token}, "error": None}


# ── GET /ext/link ─────────────────────────────────────────────────────────────
# Served by the backend and opened in Chrome by the Electron app.
# The extension content script reads the JWT from this page, stores it in
# chrome.storage, then redirects to the apply URL.
# This is the only way to hand the JWT from Electron → Chrome extension.

@router.get("/link", response_class=HTMLResponse)
async def ext_link_page(t: str, redirect: str = "", fill: str = ""):
    """
    Handoff page: Electron opens this in Chrome once per session.
    Extension reads data-jh-token, stores JWT, then navigates to redirect URL.
    No session cookie or user lookup needed — the JWT is the credential.
    """
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Linking Job Hunter…</title></head>
<body data-jh-token="{t}" data-jh-redirect="{redirect}" data-jh-fill="{fill}"
      style="margin:0;background:#0f172a;display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui;color:#67e8f9;font-size:14px">
  <div>✦ Linking Job Hunter extension…</div>
</body>
</html>""")


# ── POST /ext/pending-fill ────────────────────────────────────────────────────
# Called by the dashboard when user clicks "Open & Auto-Fill".
# Stores a pending fill in Redis keyed by user_id and fill_id.

class CreatePendingFillBody(BaseModel):
    app_id: str
    apply_url: str
    job_title: str | None = None
    company: str | None = None


@router.post("/pending-fill", response_model=dict)
async def create_pending_fill(
    body: CreatePendingFillBody,
    raw_token: str = Depends(get_raw_token),
    db: AsyncSession = Depends(get_db),
):
    user_id = decode_token(raw_token)
    app, listing = await _get_app_for_user(body.app_id, user_id, db)

    fill_id = str(uuid.uuid4())
    campaign_id = str(app.campaign_id)

    data = {
        "fillId": fill_id,
        "appId": body.app_id,
        "campaignId": campaign_id,
        "applyUrl": body.apply_url,
        "jobTitle": body.job_title or listing.title,
        "company": body.company or listing.company,
        "status": "waiting",
        "jwt": raw_token,
    }
    # Per-user key: only one pending fill at a time
    await cache_set(f"ext:pending:user:{user_id}", data, ttl=PENDING_FILL_TTL)
    # Per-fill-id key: for status polling by the frontend
    await cache_set(f"ext:pending:fill:{fill_id}", data, ttl=PENDING_FILL_TTL)

    return {"data": {"fillId": fill_id}, "error": None}


# ── GET /ext/pending-fill/active ──────────────────────────────────────────────
# Polled by the extension every 3s. Returns the pending fill if one exists.
# The extension uses the JWT it stored from the dashboard to authenticate.

@router.get("/pending-fill/active", response_model=dict)
async def get_active_pending_fill(
    user_id: str = Depends(get_user_id),
):
    payload = await cache_get(f"ext:pending:user:{user_id}")
    if not payload:
        raise HTTPException(status_code=404, detail="No pending fill")

    # Only return if status is waiting (not already being filled or done)
    if payload.get("status") not in ("waiting",):
        raise HTTPException(status_code=404, detail="No pending fill")

    return {
        "data": {
            "fillId": payload["fillId"],
            "appId": payload["appId"],
            "applyUrl": payload["applyUrl"],
            "jobTitle": payload["jobTitle"],
            "company": payload["company"],
            "jwt": payload["jwt"],
        },
        "error": None,
    }


# ── POST /ext/pending-fill/{fill_id}/answers ──────────────────────────────────
# Extension sends scanned form fields, gets back AI-generated answers.

class FillAnswersBody(BaseModel):
    fields: list[dict]


@router.post("/pending-fill/{fill_id}/answers", response_model=dict)
async def generate_pending_fill_answers(
    fill_id: str,
    body: FillAnswersBody,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    payload = await cache_get(f"ext:pending:fill:{fill_id}")
    if not payload:
        raise HTTPException(status_code=404, detail="Fill session not found or expired")

    if payload.get("status") == "done":
        raise HTTPException(status_code=409, detail="Fill already completed")

    # Mark as filling — reset TTL to full window (in-memory cache has no TTL query)
    payload["status"] = "filling"
    await cache_set(f"ext:pending:fill:{fill_id}", payload, ttl=PENDING_FILL_TTL)
    await cache_set(f"ext:pending:user:{user_id}", payload, ttl=PENDING_FILL_TTL)

    app, listing = await _get_app_for_user(payload["appId"], user_id, db)

    svc = ApplyChatService(db)
    answers = await svc.generate_form_answers(app, listing, body.fields)

    return {"data": {"answers": answers}, "error": None}


# ── PATCH /ext/pending-fill/{fill_id}/status ─────────────────────────────────
# Extension reports final fill result (done / error).

class UpdateFillStatusBody(BaseModel):
    status: str           # "done" | "error"
    filled: int | None = None
    needs_review: int | None = None
    resume_uploaded: bool | None = None
    error: str | None = None


@router.patch("/pending-fill/{fill_id}/status", response_model=dict)
async def update_pending_fill_status(
    fill_id: str,
    body: UpdateFillStatusBody,
    user_id: str = Depends(get_user_id),
):
    payload = await cache_get(f"ext:pending:fill:{fill_id}")
    if not payload:
        raise HTTPException(status_code=404, detail="Fill session not found or expired")

    payload["status"] = body.status
    if body.filled is not None:
        payload["filled"] = body.filled
    if body.needs_review is not None:
        payload["needsReview"] = body.needs_review
    if body.resume_uploaded is not None:
        payload["resumeUploaded"] = body.resume_uploaded
    if body.error is not None:
        payload["error"] = body.error

    # Reset TTL to full window (in-memory cache has no TTL query)
    await cache_set(f"ext:pending:fill:{fill_id}", payload, ttl=PENDING_FILL_TTL)
    await cache_set(f"ext:pending:user:{user_id}", payload, ttl=PENDING_FILL_TTL)

    return {"data": {"ok": True}, "error": None}


# ── GET /ext/pending-fill/{fill_id}/status ───────────────────────────────────
# Polled by the frontend to show live status to the user.

@router.get("/pending-fill/{fill_id}/status", response_model=dict)
async def get_pending_fill_status(
    fill_id: str,
    user_id: str = Depends(get_user_id),
):
    payload = await cache_get(f"ext:pending:fill:{fill_id}")
    if not payload:
        raise HTTPException(status_code=404, detail="Fill session expired")

    return {
        "data": {
            "status": payload.get("status", "waiting"),
            "filled": payload.get("filled"),
            "needsReview": payload.get("needsReview"),
            "resumeUploaded": payload.get("resumeUploaded"),
            "error": payload.get("error"),
        },
        "error": None,
    }


# ── GET /ext/match ───────────────────────────────────────────────────────────
# Called by the extension on every page load. Returns job + application info
# if the current page URL matches a listing in the user's pipeline.

@router.get("/match", response_model=dict)
async def match_url(
    url: str,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Match the current browser URL against job_listings.url and job_listings.apply_url.
    Strips query params and fragment before matching — handles tracking params, UTMs, etc.
    Returns the job + application if found, 404 otherwise.
    """
    from urllib.parse import urlparse, urlunparse

    import re as _re

    def normalise(raw: str) -> str:
        try:
            p = urlparse(raw)
            return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', '', ''))
        except Exception:
            return raw.rstrip('/')

    clean_url = normalise(url)
    base_url  = clean_url.removesuffix('/apply')

    # Extract all numeric segments from the path (ATS job IDs are numeric)
    # e.g. stripe.com/jobs/listing/staff-full-stack.../7925073/apply → ["7925073"]
    # greenhouse.io/stripe/jobs/7925073 → ["7925073"]
    job_ids = _re.findall(r'\b(\d{6,})\b', urlparse(url).path)

    def base_query():
        return (
            select(JobListing, Application, JobHunterCampaign)
            .join(JobHunterCampaign, JobListing.campaign_id == JobHunterCampaign.id)
            .outerjoin(
                Application,
                (Application.job_listing_id == JobListing.id) &
                (Application.user_id == user_id) &
                (Application.deleted_at.is_(None)),
            )
            .where(
                JobHunterCampaign.user_id == user_id,
                JobHunterCampaign.deleted_at.is_(None),
                JobListing.deleted_at.is_(None),
            )
        )

    row = None

    # 1. Exact URL match (same domain — direct hit)
    for pattern in [clean_url, clean_url + '%', base_url, base_url + '%']:
        result = await db.execute(
            base_query().where(
                (JobListing.url.ilike(pattern)) |
                (JobListing.apply_url.ilike(pattern))
            ).limit(1)
        )
        row = result.one_or_none()
        if row:
            break

    # 2. Job ID match (cross-domain: stripe.com listing → greenhouse.io apply URL)
    if not row and job_ids:
        from sqlalchemy import or_
        id_filters = or_(*(
            (JobListing.url.ilike(f'%/{jid}%')) |
            (JobListing.apply_url.ilike(f'%/{jid}%'))
            for jid in job_ids
        ))
        result = await db.execute(base_query().where(id_filters).limit(1))
        row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="No matching job found")

    listing, application, campaign = row.JobListing, row.Application, row.JobHunterCampaign

    return {
        "data": {
            "listingId": listing.id,
            "appId": application.id if application else None,
            "campaignId": str(listing.campaign_id),
            "jobTitle": listing.title,
            "company": listing.company,
            "applyUrl": listing.apply_url or listing.url,
            "matchScore": listing.match_score,
            "appStatus": application.status if application else None,
            "hasResume": bool(application and application.tailored_resume_pdf_url) if application else False,
        },
        "error": None,
    }


# ── GET /ext/applications/{app_id} ───────────────────────────────────────────

@router.get("/applications/{app_id}", response_model=dict)
async def get_ext_application(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    app, listing = await _get_app_for_user(app_id, user_id, db)
    return {
        "data": {
            "applyUrl": listing.apply_url or listing.url,
            "resumeUrl": f"/api/v1/job-hunter/ext/applications/{app_id}/resume",
            "jobTitle": listing.title,
            "company": listing.company,
            "coverLetter": app.cover_letter,
        },
        "error": None,
    }


# ── POST /ext/applications/{app_id}/generate-form-answers ────────────────────

class FormField(BaseModel):
    label: str
    type: str
    options: list[str] | None = None


class GenerateFormAnswersRequest(BaseModel):
    fields: list[FormField]


@router.post("/applications/{app_id}/generate-form-answers", response_model=dict)
async def generate_form_answers(
    app_id: str,
    body: GenerateFormAnswersRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    app, listing = await _get_app_for_user(app_id, user_id, db)
    fields = [f.model_dump() for f in body.fields]
    svc = ApplyChatService(db)
    answers = await svc.generate_form_answers(app, listing, fields)
    return {"data": {"answers": answers}, "error": None}


# ── GET /ext/applications/{app_id}/resume ────────────────────────────────────

@router.get("/applications/{app_id}/resume")
async def get_ext_resume(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    app, _ = await _get_app_for_user(app_id, user_id, db)

    if not app.tailored_resume_pdf_url:
        raise HTTPException(status_code=404, detail="No tailored resume for this application")

    backend_root = Path(__file__).resolve().parents[4]
    pdf_path = backend_root / app.tailored_resume_pdf_url

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename="resume.pdf",
    )
