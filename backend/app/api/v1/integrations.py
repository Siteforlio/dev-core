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
from app.schemas.job_hunter import EmailCredentialsRequest, CalDAVCredentialsRequest, LinkedInCredentialsRequest, EmailSendRequest
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


@router.get("/caldav/events", response_model=dict)
async def get_caldav_events(
    start: str,
    end: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Fetch calendar events for a date range (YYYY-MM-DD). Returns empty list if CalDAV not configured."""
    import asyncio
    row = await _get_or_create(db, user_id)
    if not row.caldav_account_encrypted:
        return {"data": {"events": [], "configured": False}, "error": None}
    creds = EmailService(db).decrypt_credentials(row.caldav_account_encrypted)

    def _fetch() -> list[dict]:
        try:
            import caldav
            from datetime import datetime, timezone, date as date_type
            start_dt = datetime.fromisoformat(start).replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
            end_dt = datetime.fromisoformat(end).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            client = caldav.DAVClient(url=creds["url"], username=creds["username"], password=creds["password"])
            event_colors = ['#0f766e', '#0891b2', '#22d3ee', '#0e7490', '#155e63']
            events: list[dict] = []
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            for cal in client.principal().calendars():
                for ev in cal.date_search(start=start_dt, end=end_dt, expand=True):
                    try:
                        vevent = ev.vobject_instance.vevent
                        dtstart = vevent.dtstart.value
                        dtend = getattr(vevent, 'dtend', vevent.dtstart).value
                        # normalise to naive UTC datetime
                        if isinstance(dtstart, date_type) and not isinstance(dtstart, datetime):
                            dtstart = datetime(dtstart.year, dtstart.month, dtstart.day)
                        elif hasattr(dtstart, 'tzinfo') and dtstart.tzinfo:
                            dtstart = dtstart.astimezone(timezone.utc).replace(tzinfo=None)
                        if isinstance(dtend, date_type) and not isinstance(dtend, datetime):
                            dtend = datetime(dtend.year, dtend.month, dtend.day)
                        elif hasattr(dtend, 'tzinfo') and dtend.tzinfo:
                            dtend = dtend.astimezone(timezone.utc).replace(tzinfo=None)
                        uid = str(getattr(vevent.uid, 'value', '') if hasattr(vevent, 'uid') else '').strip()
                        summary = str(getattr(vevent.summary, 'value', '') if hasattr(vevent, 'summary') else '').strip() or 'Untitled'
                        location = str(getattr(vevent.location, 'value', '') if hasattr(vevent, 'location') else '').strip()
                        description = str(getattr(vevent.description, 'value', '') if hasattr(vevent, 'description') else '').strip()
                        # Parse ATTENDEE list
                        raw_attendees: list[dict] = []
                        if hasattr(vevent, 'attendee_list'):
                            for att in vevent.attendee_list:
                                try:
                                    addr = str(att.value).replace('mailto:', '').strip()
                                    cn = str(att.params.get('CN', [''])[0]).strip() if hasattr(att, 'params') else ''
                                    raw_attendees.append({"name": cn or addr, "email": addr})
                                except Exception:
                                    pass
                        elif hasattr(vevent, 'attendee'):
                            try:
                                att = vevent.attendee
                                addr = str(att.value).replace('mailto:', '').strip()
                                cn = str(att.params.get('CN', [''])[0]).strip() if hasattr(att, 'params') else ''
                                raw_attendees.append({"name": cn or addr, "email": addr})
                            except Exception:
                                pass
                        dur_mins = max(0, int((dtend - dtstart).total_seconds() // 60))
                        if dur_mins >= 60:
                            h, m = divmod(dur_mins, 60)
                            dur_str = f"{h}h {m}m" if m else f"{h}h"
                        else:
                            dur_str = f"{dur_mins}m"
                        color = event_colors[len(events) % len(event_colors)]
                        is_live = dtstart <= now_utc <= dtend
                        events.append({
                            "uid": uid,
                            "date": dtstart.strftime("%Y-%m-%d"),
                            "time": dtstart.strftime("%H:%M"),
                            "dtstart_iso": dtstart.strftime("%Y-%m-%dT%H:%M:%S"),
                            "dtend_iso": dtend.strftime("%Y-%m-%dT%H:%M:%S"),
                            "dur": dur_str,
                            "duration_minutes": dur_mins,
                            "title": summary,
                            "location": location,
                            "tag": location or description[:50],
                            "color": color,
                            "live": is_live,
                            "attendees": raw_attendees,
                        })
                    except Exception:
                        logger.warning("Skipping malformed CalDAV event", exc_info=True)
            return events
        except Exception:
            logger.exception("CalDAV fetch failed")
            return []

    events = await asyncio.to_thread(_fetch)
    return {"data": {"events": events, "configured": True}, "error": None}


@router.post("/email/send", response_model=dict)
async def send_email_followup(
    body: EmailSendRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Send a follow-up email using the user's stored SMTP credentials."""
    import asyncio, smtplib
    from email.mime.text import MIMEText as _MIMEText
    row = await _get_or_create(db, user_id)
    if not row.email_account_encrypted:
        raise HTTPException(
            status_code=400,
            detail="Email not configured — add your SMTP credentials in Settings first.",
        )
    creds = EmailService(db).decrypt_credentials(row.email_account_encrypted)

    def _send() -> tuple[bool, str | None]:
        try:
            msg = _MIMEText(body.body, "plain", "utf-8")
            msg["Subject"] = body.subject
            msg["From"] = creds["username"]
            msg["To"] = ", ".join(body.to)
            smtp_host = creds.get("smtp_host") or creds["host"]
            smtp_port = int(creds.get("smtp_port", 465))
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(creds["username"], creds["password"])
                server.sendmail(creds["username"], body.to, msg.as_string())
            return True, None
        except Exception as e:
            return False, str(e)

    ok, err = await asyncio.to_thread(_send)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to send: {err}")
    return {"data": {"sent": True}, "error": None}


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
