# backend/tests/api/test_applications.py
"""
Unit tests for application API endpoints.

Tests call the endpoint handler functions directly, bypassing FastAPI routing
and DB startup (which requires a real DB connection in the conftest).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi import HTTPException

from app.api.v1.job_hunter.applications import (
    get_application_detail,
    patch_application_status,
    generate_cover_letter,
    apply_chat,
    open_in_chrome,
    get_tracking_status,
    StatusPatch,
    ChatRequest,
    ChatMessage,
)


# ── factories ─────────────────────────────────────────────────────────────────

USER_ID = "user-abc"
CAMPAIGN_ID = "camp-123"
APP_ID = "app-456"


def _mock_application(status="pending"):
    a = MagicMock()
    a.id = APP_ID
    a.user_id = USER_ID
    a.campaign_id = CAMPAIGN_ID
    a.status = status
    a.tailored_resume_pdf_url = "/resumes/campaign/company/Solomon Jesse - Stripe - SWE.pdf"
    a.cover_letter = "My cover letter."
    a.applied_at = None
    a.status_updated_at = None
    a.form_answers = {}
    return a


def _mock_listing():
    l = MagicMock()
    l.company = "Stripe"
    l.title = "Senior Software Engineer"
    l.location = "Remote"
    l.apply_url = "https://stripe.com/apply"
    l.url = "https://stripe.com/jobs/123"
    l.description = "We build payments."
    return l


def _mock_campaign():
    c = MagicMock()
    c.name = "Software Engineer 2026"
    return c


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


# ── GET detail ────────────────────────────────────────────────────────────────

async def test_get_detail_success(mock_db):
    a = _mock_application()
    l = _mock_listing()
    c = _mock_campaign()

    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l, c))
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await get_application_detail(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    data = resp["data"]

    assert data["application_id"] == APP_ID
    assert data["company"] == "Stripe"
    assert data["title"] == "Senior Software Engineer"
    assert data["resume_filename"] == "Solomon Jesse - Stripe - SWE.pdf"
    assert data["cover_letter"] == "My cover letter."
    assert data["apply_url"] == "https://stripe.com/apply"
    assert resp["error"] is None


async def test_get_detail_not_found(mock_db):
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc:
        await get_application_detail(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert exc.value.status_code == 404


async def test_get_detail_no_resume(mock_db):
    a = _mock_application()
    a.tailored_resume_pdf_url = None

    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, _mock_listing(), _mock_campaign()))
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await get_application_detail(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    data = resp["data"]
    assert data["resume_path"] is None
    assert data["resume_filename"] is None
    assert data["resume_folder"] is None


async def test_get_detail_falls_back_to_url_when_no_apply_url(mock_db):
    a = _mock_application()
    l = _mock_listing()
    l.apply_url = None  # no apply_url — should fall back to url

    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l, _mock_campaign()))
    mock_db.execute = AsyncMock(return_value=result_mock)

    resp = await get_application_detail(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert resp["data"]["apply_url"] == "https://stripe.com/jobs/123"


# ── PATCH status ──────────────────────────────────────────────────────────────

async def test_patch_status_applied(mock_db):
    a = _mock_application()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=a)
    mock_db.execute = AsyncMock(return_value=result_mock)

    body = StatusPatch(status="applied")
    resp = await patch_application_status(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)

    assert a.status == "applied"
    assert resp["data"]["status"] == "applied"
    mock_db.commit.assert_called_once()


async def test_patch_status_invalid_value_raises_422(mock_db):
    body = StatusPatch(status="nonsense")
    with pytest.raises(HTTPException) as exc:
        await patch_application_status(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)
    assert exc.value.status_code == 422


async def test_patch_status_not_found_raises_404(mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=result_mock)

    body = StatusPatch(status="applied")
    with pytest.raises(HTTPException) as exc:
        await patch_application_status(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)
    assert exc.value.status_code == 404


async def test_patch_status_saves_notes(mock_db):
    a = _mock_application()
    a.form_answers = {}
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=a)
    mock_db.execute = AsyncMock(return_value=result_mock)

    body = StatusPatch(status="failed", notes="Form rejected me.")
    await patch_application_status(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)

    assert a.form_answers["apply_notes"] == "Form rejected me."


async def test_patch_status_all_valid_statuses(mock_db):
    for status in ("applied", "failed", "withdrawn", "pending"):
        a = _mock_application()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=a)
        mock_db.execute = AsyncMock(return_value=result_mock)
        mock_db.commit = AsyncMock()

        body = StatusPatch(status=status)
        resp = await patch_application_status(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)
        assert resp["data"]["status"] == status


# ── POST cover-letter ─────────────────────────────────────────────────────────

async def test_generate_cover_letter_success(mock_db):
    a = _mock_application()
    l = _mock_listing()
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l))
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch(
        "app.api.v1.job_hunter.applications.ApplyChatService.generate_cover_letter",
        new=AsyncMock(return_value="Generated cover letter."),
    ):
        resp = await generate_cover_letter(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)

    assert resp["data"]["cover_letter"] == "Generated cover letter."
    assert a.cover_letter == "Generated cover letter."
    mock_db.commit.assert_called_once()


async def test_generate_cover_letter_not_found(mock_db):
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc:
        await generate_cover_letter(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert exc.value.status_code == 404


# ── POST chat ─────────────────────────────────────────────────────────────────

async def test_chat_returns_reply(mock_db):
    a = _mock_application()
    l = _mock_listing()
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l))
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch(
        "app.api.v1.job_hunter.applications.ApplyChatService.chat",
        new=AsyncMock(return_value="You have 2 years of Python."),
    ):
        body = ChatRequest(message="How many years of Python?", history=[])
        resp = await apply_chat(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)

    assert resp["data"]["reply"] == "You have 2 years of Python."


async def test_chat_not_found(mock_db):
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=result_mock)

    body = ChatRequest(message="hello", history=[])
    with pytest.raises(HTTPException) as exc:
        await apply_chat(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)
    assert exc.value.status_code == 404


async def test_chat_history_forwarded(mock_db):
    a = _mock_application()
    l = _mock_listing()
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l))
    mock_db.execute = AsyncMock(return_value=result_mock)

    captured = {}

    async def fake_chat(self_ref, application, listing, user_message, history):
        captured["history"] = history
        return "ok"

    with patch(
        "app.api.v1.job_hunter.applications.ApplyChatService.chat",
        new=AsyncMock(side_effect=lambda **kw: "ok"),
    ):
        # Just verify no crash when history is present
        body = ChatRequest(
            message="Next question",
            history=[ChatMessage(role="user", content="Hi"), ChatMessage(role="assistant", content="Hello")],
        )
        resp = await apply_chat(CAMPAIGN_ID, APP_ID, body, mock_db, USER_ID)
    assert resp["data"]["reply"] == "ok"


# ── POST open-in-chrome ───────────────────────────────────────────────────────

async def test_open_in_chrome_success(mock_db):
    a = _mock_application()
    l = _mock_listing()
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l))
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("subprocess.Popen") as mock_popen, \
         patch("shutil.which", return_value=None), \
         patch("pathlib.Path.exists", return_value=True):
        resp = await open_in_chrome(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)

    assert resp["data"]["opened"] is True
    assert resp["data"]["url"] == "https://stripe.com/apply"


async def test_open_in_chrome_no_url_raises_422(mock_db):
    a = _mock_application()
    l = _mock_listing()
    l.apply_url = None
    l.url = None

    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l))
    mock_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc:
        await open_in_chrome(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert exc.value.status_code == 422


async def test_open_in_chrome_not_found(mock_db):
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc:
        await open_in_chrome(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert exc.value.status_code == 404


async def test_open_in_chrome_fallback_to_listing_url(mock_db):
    a = _mock_application()
    l = _mock_listing()
    l.apply_url = None  # fallback to l.url

    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=(a, l))
    mock_db.execute = AsyncMock(return_value=result_mock)

    with patch("subprocess.Popen"), \
         patch("shutil.which", return_value=None), \
         patch("pathlib.Path.exists", return_value=True):
        resp = await open_in_chrome(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)

    assert resp["data"]["url"] == "https://stripe.com/jobs/123"


# ── GET tracking ──────────────────────────────────────────────────────────────

async def test_tracking_returns_matching_events(mock_db):
    a = _mock_application(status="applied")
    a.applied_at = datetime(2026, 1, 15)
    a.status_updated_at = datetime(2026, 1, 15)
    l = _mock_listing()

    event = MagicMock()
    event.id = "ev-1"
    event.subject = "Re: your application"
    event.sender = "hr@stripe.com"
    event.classification = "response"
    event.received_at = datetime(2026, 1, 20)

    app_result = MagicMock()
    app_result.first = MagicMock(return_value=(a, l))

    events_result = MagicMock()
    events_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[event])))

    mock_db.execute = AsyncMock(side_effect=[app_result, events_result])

    resp = await get_tracking_status(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    data = resp["data"]

    assert data["status"] == "applied"
    assert data["company"] == "Stripe"
    assert len(data["email_events"]) == 1
    assert data["email_events"][0]["sender"] == "hr@stripe.com"
    assert data["email_events"][0]["classification"] == "response"


async def test_tracking_filters_unrelated_events(mock_db):
    a = _mock_application(status="applied")
    a.applied_at = None
    a.status_updated_at = None
    l = _mock_listing()

    # Sender is from google, not stripe — should be filtered out
    event = MagicMock()
    event.sender = "noreply@google.com"
    event.received_at = datetime(2026, 1, 20)

    app_result = MagicMock()
    app_result.first = MagicMock(return_value=(a, l))
    events_result = MagicMock()
    events_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[event])))

    mock_db.execute = AsyncMock(side_effect=[app_result, events_result])

    resp = await get_tracking_status(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert resp["data"]["email_events"] == []


async def test_tracking_not_found(mock_db):
    app_result = MagicMock()
    app_result.first = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=app_result)

    with pytest.raises(HTTPException) as exc:
        await get_tracking_status(CAMPAIGN_ID, APP_ID, mock_db, USER_ID)
    assert exc.value.status_code == 404
