# backend/app/services/microsoft_oauth_service.py
"""
Microsoft OAuth 2.0 (MSAL) service — Graph Calendar + Graph Mail.
"""
import json
import logging
import secrets
import time
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["Calendars.Read", "Mail.Send", "User.Read"]

_pending_states: dict[str, str] = {}

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _fernet() -> Fernet:
    if not settings.job_hunter_encryption_key:
        raise ValueError("JOB_HUNTER_ENCRYPTION_KEY not configured")
    return Fernet(settings.job_hunter_encryption_key.encode())


def encrypt_token(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_token(encrypted: str) -> dict:
    return json.loads(_fernet().decrypt(encrypted.encode()).decode())


def is_configured() -> bool:
    return bool(settings.microsoft_client_id and settings.microsoft_client_secret)


def _app():
    import msal
    return msal.ConfidentialClientApplication(
        client_id=settings.microsoft_client_id,
        client_credential=settings.microsoft_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}",
    )


def get_auth_url(user_id: str, redirect_uri: str) -> str:
    state = secrets.token_urlsafe(32)
    _pending_states[user_id] = state
    url = _app().get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )
    return url


def exchange_code(user_id: str, code: str, state: str, redirect_uri: str) -> dict:
    expected = _pending_states.pop(user_id, None)
    if not expected or expected != state:
        raise ValueError("Invalid OAuth state — possible CSRF attempt")

    result = _app().acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    if "error" in result:
        raise ValueError(f"Microsoft token error: {result.get('error_description', result['error'])}")

    expires_at = time.time() + result.get("expires_in", 3600)
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "expires_at": expires_at,
        "scope": result.get("scope", "").split(),
    }


def _get_valid_token(token_data: dict) -> tuple[str, dict]:
    """Return a valid access token, refreshing if needed. Returns (token, updated_data)."""
    if time.time() < token_data.get("expires_at", 0) - 60:
        return token_data["access_token"], token_data

    result = _app().acquire_token_by_refresh_token(
        refresh_token=token_data["refresh_token"],
        scopes=SCOPES,
    )
    if "error" in result:
        raise ValueError(f"Microsoft refresh error: {result.get('error_description', result['error'])}")

    expires_at = time.time() + result.get("expires_in", 3600)
    updated = {
        **token_data,
        "access_token": result["access_token"],
        "expires_at": expires_at,
    }
    if result.get("refresh_token"):
        updated["refresh_token"] = result["refresh_token"]
    return updated["access_token"], updated


def fetch_calendar_events(token_data: dict, start_date: str, end_date: str) -> tuple[list[dict], dict]:
    """
    Fetch events from Microsoft Graph Calendar.
    Returns (events, updated_token_data).
    """
    import httpx
    from datetime import datetime, timezone

    access_token, token_data = _get_valid_token(token_data)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    time_min = f"{start_date}T00:00:00Z"
    time_max = f"{end_date}T23:59:59Z"

    url = (
        f"{GRAPH_BASE}/me/calendarView"
        f"?startDateTime={time_min}&endDateTime={time_max}"
        f"&$select=id,subject,start,end,location,attendees,bodyPreview"
        f"&$orderby=start/dateTime"
        f"&$top=100"
    )

    event_colors = ["#0f766e", "#0891b2", "#22d3ee", "#0e7490", "#155e63"]
    events: list[dict] = []
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    with httpx.Client(timeout=15) as client:
        while url:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for ev in data.get("value", []):
                try:
                    start_str = ev["start"]["dateTime"]
                    end_str = ev["end"]["dateTime"]
                    dtstart = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                    dtend = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                    dur_mins = max(0, int((dtend - dtstart).total_seconds() // 60))
                    h, m = divmod(dur_mins, 60)
                    dur_str = f"{h}h {m}m" if m and h else (f"{h}h" if h else f"{m}m")
                    attendees = [
                        {
                            "name": a.get("emailAddress", {}).get("name", ""),
                            "email": a.get("emailAddress", {}).get("address", ""),
                        }
                        for a in ev.get("attendees", [])
                    ]
                    location = ev.get("location", {}).get("displayName", "")
                    color = event_colors[len(events) % len(event_colors)]
                    is_live = dtstart <= now_utc <= dtend
                    events.append({
                        "uid": ev.get("id", ""),
                        "date": dtstart.strftime("%Y-%m-%d"),
                        "time": dtstart.strftime("%H:%M"),
                        "dtstart_iso": dtstart.strftime("%Y-%m-%dT%H:%M:%S"),
                        "dtend_iso": dtend.strftime("%Y-%m-%dT%H:%M:%S"),
                        "dur": dur_str,
                        "duration_minutes": dur_mins,
                        "title": ev.get("subject", "Untitled"),
                        "location": location,
                        "tag": location or "Microsoft Calendar",
                        "color": color,
                        "live": is_live,
                        "attendees": attendees,
                    })
                except Exception:
                    logger.warning("Skipping malformed Graph Calendar event", exc_info=True)
            url = data.get("@odata.nextLink")

    return events, token_data


def send_email(token_data: dict, to: list[str], subject: str, body: str) -> tuple[bool, dict]:
    """Send email via Microsoft Graph Mail API."""
    import httpx

    access_token, token_data = _get_valid_token(token_data)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
        }
    }

    with httpx.Client(timeout=15) as client:
        resp = client.post(f"{GRAPH_BASE}/me/sendMail", json=payload, headers=headers)
        resp.raise_for_status()

    return True, token_data
