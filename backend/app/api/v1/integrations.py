# backend/app/api/v1/integrations.py
"""
Global user-level integration settings.
Credentials stored once here; campaigns just toggle them on/off.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.pg.job_hunter import UserIntegration
from app.schemas.job_hunter import EmailCredentialsRequest, CalDAVCredentialsRequest, LinkedInCredentialsRequest
from app.services.job_hunter.email_service import EmailService

router = APIRouter(prefix="/integrations", tags=["integrations"])
bearer = HTTPBearer()


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


@router.get("/status", response_model=dict)
async def get_status(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    """Returns which integrations are configured for this user."""
    row = await _get_or_create(db, user_id)
    return {"data": {
        "email_configured": bool(row.email_account_encrypted),
        "caldav_configured": bool(row.caldav_account_encrypted),
        "linkedin_configured": bool(row.linkedin_account_encrypted),
    }, "error": None}


@router.put("/email", response_model=dict)
async def set_email(
    body: EmailCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    row = await _get_or_create(db, user_id)
    creds = body.model_dump()
    if not creds.get("smtp_host"):
        creds["smtp_host"] = creds["host"]
    from datetime import datetime, timezone
    row.email_account_encrypted = EmailService(db).encrypt_credentials(creds)
    row.email_monitor_since = datetime.now(timezone.utc).replace(tzinfo=None)
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return {"data": {"configured": True}, "error": None}


@router.post("/email/test", response_model=dict)
async def test_email(body: EmailCredentialsRequest, user_id: str = Depends(get_user_id)):
    import asyncio, imaplib
    def _test():
        try:
            mail = imaplib.IMAP4_SSL(body.host, body.port)
            mail.login(body.username, body.password)
            mail.logout()
            return True, None
        except imaplib.IMAP4.error as e:
            hint = ""
            if "gmail" in body.host.lower():
                hint = " — For Gmail: use an App Password (myaccount.google.com/apppasswords) and enable IMAP in Gmail settings."
            return False, f"Authentication failed: {e}{hint}"
        except OSError as e:
            return False, f"Cannot reach {body.host}:{body.port} — check the hostname and that port 993 is not blocked."
        except Exception as e:
            return False, str(e)
    ok, err = await asyncio.to_thread(_test)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"data": {"ok": True}, "error": None}


@router.put("/caldav", response_model=dict)
async def set_caldav(
    body: CalDAVCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    from datetime import datetime, timezone
    row = await _get_or_create(db, user_id)
    row.caldav_account_encrypted = EmailService(db).encrypt_credentials(body.model_dump())
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return {"data": {"configured": True}, "error": None}


@router.post("/caldav/test", response_model=dict)
async def test_caldav(body: CalDAVCredentialsRequest, user_id: str = Depends(get_user_id)):
    import asyncio
    def _test():
        try:
            import caldav
            client = caldav.DAVClient(url=body.url, username=body.username, password=body.password)
            calendars = client.principal().calendars()
            return True, f"Connected — {len(calendars)} calendar(s) found"
        except Exception as e:
            return False, str(e)
    ok, msg = await asyncio.to_thread(_test)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"data": {"ok": True, "message": msg}, "error": None}


@router.put("/linkedin", response_model=dict)
async def set_linkedin(
    body: LinkedInCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    from datetime import datetime, timezone
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
    """
    Lightweight validation — just checks credentials are present and well-formed.
    Full auth is verified on first scrape run to avoid launching a browser on every save.
    """
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
