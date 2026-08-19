# backend/app/api/v1/integrations.py
"""
Global user-level integration settings.
Google and Microsoft OAuth replace manual CalDAV/IMAP/SMTP config.
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.pg.job_hunter import UserIntegration
from app.schemas.job_hunter import LinkedInCredentialsRequest, EmailSendRequest
from app.services.job_hunter.email_service import EmailService
import app.services.google_oauth_service as google_svc
import app.services.microsoft_oauth_service as ms_svc

router = APIRouter(prefix="/integrations", tags=["integrations"])
bearer = HTTPBearer()
logger = logging.getLogger(__name__)

_CALLBACK_HTML = """<!DOCTYPE html>
<html>
<head><title>DevCore — Connected</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;color:#e2e8f0}}
.box{{text-align:center}}.icon{{font-size:3rem}}.msg{{font-size:1.2rem;margin-top:1rem}}</style>
</head>
<body><div class="box"><div class="icon">✓</div>
<div class="msg"><strong>{provider}</strong> connected to DevCore.<br>You can close this tab.</div></div></body>
</html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html>
<head><title>DevCore — Error</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;color:#e2e8f0}}
.box{{text-align:center;max-width:500px}}.icon{{font-size:3rem}}.msg{{font-size:1rem;margin-top:1rem;color:#f87171}}</style>
</head>
<body><div class="box"><div class="icon">✗</div>
<div class="msg"><strong>OAuth error:</strong><br>{detail}<br><br>You can close this tab and try again in DevCore.</div></div></body>
</html>"""


def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


async def _get_or_create(db: AsyncSession, user_id: str) -> UserIntegration:
    result = await db.execute(select(UserIntegration).where(UserIntegration.user_id == user_id))
    row = result.scalar_one_or_none()
    if not row:
        row = UserIntegration(user_id=user_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _redirect_uri(request: Request, provider: str) -> str:
    """Build the OAuth redirect URI.
    Always uses 'localhost' (not '127.0.0.1') so the URI matches
    what users register in Azure Portal (http://localhost).
    """
    port = request.url.port or 8000
    return f"http://localhost:{port}/api/v1/integrations/oauth/{provider}/callback"


# ─── Status ──────────────────────────────────────────────────────────────────

@router.get("/status", response_model=dict)
async def get_status(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    row = await _get_or_create(db, user_id)
    return {"data": {
        "google_configured": bool(row.google_oauth_encrypted),
        "microsoft_configured": bool(row.microsoft_oauth_encrypted),
        "linkedin_configured": bool(row.linkedin_account_encrypted),
    }, "error": None}


@router.get("/oauth/setup", response_model=dict)
async def get_oauth_setup(_: str = Depends(get_user_id)):
    """Returns whether server-side OAuth client credentials are configured."""
    return {"data": {
        "google_ready": google_svc.is_configured(),
        "microsoft_ready": ms_svc.is_configured(),
    }, "error": None}


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@router.get("/oauth/google/url", response_model=dict)
async def google_auth_url(request: Request, user_id: str = Depends(get_user_id)):
    if not google_svc.is_configured():
        raise HTTPException(status_code=400, detail="Google OAuth credentials not configured in server settings.")
    redirect_uri = _redirect_uri(request, "google")
    url = await asyncio.to_thread(google_svc.get_auth_url, user_id, redirect_uri)
    return {"data": {"url": url}, "error": None}


@router.get("/oauth/google/callback", response_class=HTMLResponse)
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handles Google redirect. Extracts user_id from state, exchanges code, stores tokens.
    No JWT auth here — request comes from the system browser.
    """
    params = dict(request.query_params)
    code = params.get("code")
    state = params.get("state")
    error = params.get("error")

    if error:
        return HTMLResponse(_ERROR_HTML.format(detail=error), status_code=400)
    if not code or not state:
        return HTMLResponse(_ERROR_HTML.format(detail="Missing code or state parameter."), status_code=400)

    # Recover user_id by scanning pending states (desktop app = single user, safe)
    user_id = next((uid for uid, s in google_svc._pending_states.items() if s == state), None)
    if not user_id:
        return HTMLResponse(_ERROR_HTML.format(detail="OAuth session expired or invalid. Please try again."), status_code=400)

    try:
        redirect_uri = _redirect_uri(request, "google")
        token_data = await asyncio.to_thread(google_svc.exchange_code, user_id, code, state, redirect_uri)
        encrypted = google_svc.encrypt_token(token_data)

        result = await db.execute(select(UserIntegration).where(UserIntegration.user_id == user_id))
        row = result.scalar_one_or_none()
        if not row:
            row = UserIntegration(user_id=user_id)
            db.add(row)
        row.google_oauth_encrypted = encrypted
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
    except Exception as e:
        logger.exception("Google OAuth callback failed")
        return HTMLResponse(_ERROR_HTML.format(detail=str(e)), status_code=500)

    return HTMLResponse(_CALLBACK_HTML.format(provider="Google"))


@router.delete("/oauth/google", response_model=dict)
async def google_disconnect(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    row = await _get_or_create(db, user_id)
    row.google_oauth_encrypted = None
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return {"data": {"disconnected": True}, "error": None}


# ─── Microsoft OAuth ──────────────────────────────────────────────────────────

@router.get("/oauth/microsoft/url", response_model=dict)
async def microsoft_auth_url(request: Request, user_id: str = Depends(get_user_id)):
    if not ms_svc.is_configured():
        raise HTTPException(status_code=400, detail="Microsoft OAuth credentials not configured in server settings.")
    redirect_uri = _redirect_uri(request, "microsoft")
    url = await asyncio.to_thread(ms_svc.get_auth_url, user_id, redirect_uri)
    return {"data": {"url": url}, "error": None}


@router.get("/oauth/microsoft/callback", response_class=HTMLResponse)
async def microsoft_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    params = dict(request.query_params)
    code = params.get("code")
    state = params.get("state")
    error = params.get("error")
    error_description = params.get("error_description", "")

    if error:
        return HTMLResponse(_ERROR_HTML.format(detail=error_description or error), status_code=400)
    if not code or not state:
        return HTMLResponse(_ERROR_HTML.format(detail="Missing code or state parameter."), status_code=400)

    user_id = next((uid for uid, s in ms_svc._pending_states.items() if s == state), None)
    if not user_id:
        return HTMLResponse(_ERROR_HTML.format(detail="OAuth session expired or invalid. Please try again."), status_code=400)

    try:
        redirect_uri = _redirect_uri(request, "microsoft")
        token_data = await asyncio.to_thread(ms_svc.exchange_code, user_id, code, state, redirect_uri)
        encrypted = ms_svc.encrypt_token(token_data)

        result = await db.execute(select(UserIntegration).where(UserIntegration.user_id == user_id))
        row = result.scalar_one_or_none()
        if not row:
            row = UserIntegration(user_id=user_id)
            db.add(row)
        row.microsoft_oauth_encrypted = encrypted
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
    except Exception as e:
        logger.exception("Microsoft OAuth callback failed")
        return HTMLResponse(_ERROR_HTML.format(detail=str(e)), status_code=500)

    return HTMLResponse(_CALLBACK_HTML.format(provider="Microsoft"))


@router.delete("/oauth/microsoft", response_model=dict)
async def microsoft_disconnect(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    row = await _get_or_create(db, user_id)
    row.microsoft_oauth_encrypted = None
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return {"data": {"disconnected": True}, "error": None}


# ─── Calendar Events (merged Google + Microsoft) ──────────────────────────────

@router.get("/caldav/events", response_model=dict)
async def get_calendar_events(
    start: str,
    end: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Fetch calendar events from all connected providers. Returns empty list if none configured."""
    row = await _get_or_create(db, user_id)
    all_events: list[dict] = []
    configured = False

    if row.google_oauth_encrypted:
        configured = True
        try:
            token_data = google_svc.decrypt_token(row.google_oauth_encrypted)
            events, updated = await asyncio.to_thread(google_svc.fetch_calendar_events, token_data, start, end)
            all_events.extend(events)
            # Persist refreshed token if it changed
            if updated.get("token") != token_data.get("token"):
                row.google_oauth_encrypted = google_svc.encrypt_token(updated)
                await db.commit()
        except Exception:
            logger.exception("Google Calendar fetch failed")

    if row.microsoft_oauth_encrypted:
        configured = True
        try:
            token_data = ms_svc.decrypt_token(row.microsoft_oauth_encrypted)
            events, updated = await asyncio.to_thread(ms_svc.fetch_calendar_events, token_data, start, end)
            all_events.extend(events)
            if updated.get("access_token") != token_data.get("access_token"):
                row.microsoft_oauth_encrypted = ms_svc.encrypt_token(updated)
                await db.commit()
        except Exception:
            logger.exception("Microsoft Calendar fetch failed")

    # Sort merged events by start time
    all_events.sort(key=lambda e: e.get("dtstart_iso", ""))
    return {"data": {"events": all_events, "configured": configured}, "error": None}


# ─── Email Send (Google preferred, Microsoft fallback) ────────────────────────

@router.post("/email/send", response_model=dict)
async def send_email(
    body: EmailSendRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    row = await _get_or_create(db, user_id)

    if row.google_oauth_encrypted:
        try:
            token_data = google_svc.decrypt_token(row.google_oauth_encrypted)
            ok, updated = await asyncio.to_thread(google_svc.send_email, token_data, body.to, body.subject, body.body)
            if updated.get("token") != token_data.get("token"):
                row.google_oauth_encrypted = google_svc.encrypt_token(updated)
                await db.commit()
            return {"data": {"sent": True}, "error": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gmail send failed: {e}")

    if row.microsoft_oauth_encrypted:
        try:
            token_data = ms_svc.decrypt_token(row.microsoft_oauth_encrypted)
            ok, updated = await asyncio.to_thread(ms_svc.send_email, token_data, body.to, body.subject, body.body)
            if updated.get("access_token") != token_data.get("access_token"):
                row.microsoft_oauth_encrypted = ms_svc.encrypt_token(updated)
                await db.commit()
            return {"data": {"sent": True}, "error": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Graph Mail send failed: {e}")

    raise HTTPException(
        status_code=400,
        detail="No email provider connected — link Google or Microsoft in Settings first.",
    )


# ─── LinkedIn (unchanged) ─────────────────────────────────────────────────────

@router.put("/linkedin", response_model=dict)
async def set_linkedin(
    body: LinkedInCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    try:
        body.mode()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    row = await _get_or_create(db, user_id)
    row.linkedin_account_encrypted = EmailService(db).encrypt_credentials(body.model_dump(exclude_none=True))
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return {"data": {"configured": True}, "error": None}


@router.post("/linkedin/test", response_model=dict)
async def test_linkedin(body: LinkedInCredentialsRequest, user_id: str = Depends(get_user_id)):
    try:
        mode = body.mode()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if mode == "cookie":
        cookie = (body.session_cookie or "").strip()
        if len(cookie) < 20:
            raise HTTPException(status_code=400, detail="Cookie value looks too short — paste the full li_at value")
    else:
        if not body.email or "@" not in body.email:
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        if not body.password or len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password looks too short")
    return {"data": {"ok": True, "mode": mode}, "error": None}
