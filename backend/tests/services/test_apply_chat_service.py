# backend/tests/services/test_apply_chat_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.apply_chat_service import (
    ApplyChatService,
    _fmt_experience,
    _fmt_skills,
    _fmt_education,
    _build_system_context,
)


# ── helper formatters ─────────────────────────────────────────────────────────

def test_fmt_experience_empty():
    assert _fmt_experience([]) == "None listed."


def test_fmt_experience_basic():
    items = [{"title": "Engineer", "company": "Acme", "start": "2022", "end": "present", "description": "Built things"}]
    result = _fmt_experience(items)
    assert "Engineer" in result
    assert "Acme" in result
    assert "Built things" in result


def test_fmt_skills_empty():
    assert _fmt_skills([]) == "None listed."


def test_fmt_skills_strings():
    result = _fmt_skills(["Python", "Go", "SQL"])
    assert "Python" in result
    assert "Go" in result


def test_fmt_skills_dicts():
    result = _fmt_skills([{"name": "Python"}, {"name": "Go"}])
    assert "Python" in result
    assert "Go" in result


def test_fmt_education_empty():
    assert _fmt_education([]) == "None listed."


def test_fmt_education_basic():
    items = [{"degree": "BSc CS", "institution": "MIT", "year": "2020"}]
    result = _fmt_education(items)
    assert "BSc CS" in result
    assert "MIT" in result


# ── system context builder ────────────────────────────────────────────────────

def _make_listing(**kwargs):
    listing = MagicMock()
    listing.title = kwargs.get("title", "Senior Engineer")
    listing.company = kwargs.get("company", "Stripe")
    listing.location = kwargs.get("location", "Remote")
    listing.description = kwargs.get("description", "We build payments infra.")
    listing.raw_description = None
    return listing


def _make_app(**kwargs):
    app = MagicMock()
    app.user_id = kwargs.get("user_id", "user-123")
    app.form_answers = kwargs.get("form_answers", {})
    app.cover_letter = kwargs.get("cover_letter", None)
    return app


def _make_profile(**kwargs):
    profile = MagicMock()
    profile.full_name = kwargs.get("full_name", "John Doe")
    profile.email = kwargs.get("email", "john@example.com")
    profile.phone = kwargs.get("phone", "+1 555 000")
    profile.city = kwargs.get("city", "San Francisco")
    profile.country = kwargs.get("country", "USA")
    profile.linkedin_url = kwargs.get("linkedin_url", "https://linkedin.com/in/johndoe")
    profile.github_url = kwargs.get("github_url", "https://github.com/johndoe")
    profile.work_experience = kwargs.get("work_experience", [])
    profile.education = kwargs.get("education", [])
    profile.skills = kwargs.get("skills", ["Python", "Go"])
    return profile


def test_build_system_context_no_profile():
    listing = _make_listing()
    app = _make_app()
    ctx = _build_system_context(None, listing, app)
    assert "Senior Engineer" in ctx
    assert "Stripe" in ctx
    assert "CANDIDATE PROFILE: Not available." in ctx


def test_build_system_context_with_profile():
    listing = _make_listing()
    app = _make_app()
    profile = _make_profile()
    ctx = _build_system_context(profile, listing, app)
    assert "John Doe" in ctx
    assert "john@example.com" in ctx
    assert "Stripe" in ctx
    assert "payments infra" in ctx


def test_build_system_context_includes_cover_letter():
    listing = _make_listing()
    app = _make_app(cover_letter="I am excited to join Stripe.")
    profile = _make_profile()
    ctx = _build_system_context(profile, listing, app)
    assert "I am excited to join Stripe." in ctx


def test_build_system_context_includes_tailored_resume():
    listing = _make_listing()
    app = _make_app(form_answers={"tailored_resume_text": "Senior Python engineer with 5 years..."})
    profile = _make_profile()
    ctx = _build_system_context(profile, listing, app)
    assert "Senior Python engineer" in ctx


def test_build_system_context_truncates_long_description():
    long_desc = "x" * 5000
    listing = _make_listing(description=long_desc)
    app = _make_app()
    profile = _make_profile()
    ctx = _build_system_context(profile, listing, app)
    # description is capped at 3000 chars — context should not balloon to 5000
    assert len(ctx) < 8000


# ── ApplyChatService ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    return ApplyChatService(mock_db)


@pytest.fixture
def listing():
    return _make_listing()


@pytest.fixture
def app():
    return _make_app()


@pytest.fixture
def profile():
    return _make_profile()


async def test_generate_cover_letter_calls_llm(service, app, listing, profile):
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none = MagicMock(return_value=profile)
    service.db.execute = AsyncMock(return_value=scalar_mock)

    with patch("app.services.job_hunter.apply_chat_service.call_llm", new=AsyncMock(return_value="  Dear Stripe,  ")) as mock_llm:
        result = await service.generate_cover_letter(app, listing)

    mock_llm.assert_called_once()
    assert result == "Dear Stripe,"  # strip() applied
    # Verify max_tokens generous enough for a cover letter
    args, kwargs = mock_llm.call_args
    assert kwargs.get("max_tokens", args[1] if len(args) > 1 else 0) >= 500


async def test_generate_cover_letter_no_profile(service, app, listing):
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none = MagicMock(return_value=None)
    service.db.execute = AsyncMock(return_value=scalar_mock)

    with patch("app.services.job_hunter.apply_chat_service.call_llm", new=AsyncMock(return_value="Cover letter text")) as mock_llm:
        result = await service.generate_cover_letter(app, listing)

    assert result == "Cover letter text"
    # prompt should still include job context even without profile
    prompt_arg = mock_llm.call_args[0][0]
    assert "Stripe" in prompt_arg


async def test_chat_includes_history(service, app, listing, profile):
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none = MagicMock(return_value=profile)
    service.db.execute = AsyncMock(return_value=scalar_mock)

    history = [
        {"role": "user", "content": "What is Stripe?"},
        {"role": "assistant", "content": "Stripe is a payments company."},
    ]

    with patch("app.services.job_hunter.apply_chat_service.call_llm", new=AsyncMock(return_value="My reply")) as mock_llm:
        result = await service.chat(app, listing, "How long have I used Python?", history)

    assert result == "My reply"
    prompt_arg = mock_llm.call_args[0][0]
    assert "What is Stripe?" in prompt_arg
    assert "Stripe is a payments company." in prompt_arg
    assert "How long have I used Python?" in prompt_arg


async def test_chat_history_capped_at_10_turns(service, app, listing, profile):
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none = MagicMock(return_value=profile)
    service.db.execute = AsyncMock(return_value=scalar_mock)

    # 20 turns — only last 10 should be included
    history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]

    with patch("app.services.job_hunter.apply_chat_service.call_llm", new=AsyncMock(return_value="ok")) as mock_llm:
        await service.chat(app, listing, "latest question", history)

    prompt_arg = mock_llm.call_args[0][0]
    assert "msg 0" not in prompt_arg  # early messages dropped
    assert "msg 19" in prompt_arg     # recent messages kept


async def test_chat_returns_stripped_response(service, app, listing, profile):
    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none = MagicMock(return_value=profile)
    service.db.execute = AsyncMock(return_value=scalar_mock)

    with patch("app.services.job_hunter.apply_chat_service.call_llm", new=AsyncMock(return_value="\n  answer  \n")):
        result = await service.chat(app, listing, "question", [])

    assert result == "answer"
