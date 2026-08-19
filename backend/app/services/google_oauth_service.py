# backend/app/services/google_oauth_service.py
"""
Google OAuth 2.0 service — Calendar + Gmail.

Token storage format (encrypted JSON):
{
  "token":         str,   # access token
  "refresh_token": str,
  "token_uri":     str,
  "client_id":     str,
  "client_secret": str,
  "scopes":        list[str],
  "expiry":        str   # ISO 8601
}
"""
import json
import logging
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Per-process CSRF state store: { user_id: state_string }
_pending_states: dict[str, str] = {}


def _fernet() -> Fernet:
    if not settings.job_hunter_encryption_key:
        raise ValueError("JOB_HUNTER_ENCRYPTION_KEY not configured")
    return Fernet(settings.job_hunter_encryption_key.encode())


def encrypt_token(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_token(encrypted: str) -> dict:
    return json.loads(_fernet().decrypt(encrypted.encode()).decode())


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def get_auth_url(user_id: str, redirect_uri: str) -> str:
    """Generate Google OAuth authorization URL and store CSRF state."""
    import secrets
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    state = secrets.token_urlsafe(32)
    _pending_states[user_id] = state
    url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
        include_granted_scopes="true",
    )
    return url


def exchange_code(user_id: str, code: str, state: str, redirect_uri: str) -> dict:
    """Exchange authorization code for tokens. Returns token dict."""
    from google_auth_oauthlib.flow import Flow

    expected = _pending_states.pop(user_id, None)
    if not expected or expected != state:
        raise ValueError("Invalid OAuth state — possible CSRF attempt")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def _build_credentials(token_data: dict):
    """Build a google.oauth2.credentials.Credentials object from stored token data."""
    from google.oauth2.credentials import Credentials
    expiry = None
    if token_data.get("expiry"):
        try:
            expiry = datetime.fromisoformat(token_data["expiry"])
        except ValueError:
            pass
    return Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id", settings.google_client_id),
        client_secret=token_data.get("client_secret", settings.google_client_secret),
        scopes=token_data.get("scopes", SCOPES),
        expiry=expiry,
    )


def _refreshed_token_data(token_data: dict) -> dict:
    """Refresh token if expired and return updated token_data dict."""
    from google.auth.transport.requests import Request

    creds = _build_credentials(token_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data = {
            **token_data,
            "token": creds.token,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
            # Persist rotated refresh token if Google issued a new one
            "refresh_token": creds.refresh_token or token_data.get("refresh_token"),
        }
    return token_data


def fetch_calendar_events(token_data: dict, start_date: str, end_date: str) -> tuple[list[dict], dict]:
    """
    Fetch events from all Google calendars for the date range.
    Returns (events, updated_token_data) — caller must re-save if token refreshed.
    """
    from googleapiclient.discovery import build

    token_data = _refreshed_token_data(token_data)
    creds = _build_credentials(token_data)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    time_min = f"{start_date}T00:00:00Z"
    time_max = f"{end_date}T23:59:59Z"

    event_colors = ["#0f766e", "#0891b2", "#22d3ee", "#0e7490", "#155e63"]
    events: list[dict] = []
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    calendars_result = service.calendarList().list().execute()
    for cal in calendars_result.get("items", []):
        cal_id = cal["id"]
        items = service.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])

        for ev in items:
            try:
                start = ev["start"].get("dateTime") or ev["start"].get("date") + "T00:00:00"
                end = ev["end"].get("dateTime") or ev["end"].get("date") + "T00:00:00"
                dtstart = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                dtend = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                dur_mins = max(0, int((dtend - dtstart).total_seconds() // 60))
                h, m = divmod(dur_mins, 60)
                dur_str = f"{h}h {m}m" if m and h else (f"{h}h" if h else f"{m}m")
                attendees = [
                    {"name": a.get("displayName", a.get("email", "")), "email": a.get("email", "")}
                    for a in ev.get("attendees", [])
                ]
                location = ev.get("location", "")
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
                    "title": ev.get("summary", "Untitled"),
                    "location": location,
                    "tag": location or cal.get("summary", ""),
                    "color": color,
                    "live": is_live,
                    "attendees": attendees,
                })
            except Exception:
                logger.warning("Skipping malformed Google Calendar event", exc_info=True)

    return events, token_data


def send_email(token_data: dict, to: list[str], subject: str, body: str) -> tuple[bool, dict]:
    """
    Send email via Gmail API.
    Returns (success, updated_token_data).
    """
    import base64
    from email.mime.text import MIMEText
    from googleapiclient.discovery import build

    token_data = _refreshed_token_data(token_data)
    creds = _build_credentials(token_data)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True, token_data
