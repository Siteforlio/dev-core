# backend/tests/services/test_board_appliers.py
"""
Unit tests for the board_appliers package.
No browser, no DB — tests the routing logic, ApplyResult contracts,
and registry completeness.
"""
import pytest
from app.services.job_hunter.board_appliers.base import ApplyResult
from app.services.job_hunter.board_appliers.registry import get_applier, APPLIER_REGISTRY
from app.services.job_hunter.board_appliers.no_apply import (
    LinkedInApplier, HNHiringApplier, KuhusteApplier, ZindiApplier,
)
from app.services.job_hunter.board_appliers.redirect_apply import (
    RedirectApplier, _detect_ats_from_url,
)
from app.services.job_hunter.board_registry import all_boards


# ── ApplyResult contract ──────────────────────────────────────────────────────

def test_apply_result_ok():
    r = ApplyResult.ok("all good")
    assert r.success is True
    assert r.skipped is False
    assert r.reason == "all good"


def test_apply_result_fail():
    r = ApplyResult.fail("form broken")
    assert r.success is False
    assert r.skipped is False


def test_apply_result_skip():
    r = ApplyResult.skip("not supported")
    assert r.success is False
    assert r.skipped is True


# ── Registry completeness ─────────────────────────────────────────────────────

def test_all_boards_have_applier():
    """Every board in the registry has an applier (or falls back gracefully)."""
    for board in all_boards():
        applier = get_applier(board.id)
        assert applier is not None, f"No applier for board {board.id}"


def test_get_applier_known_boards():
    for board_id in ["greenhouse", "lever", "ashby", "fuzu", "brightermonday",
                     "andela", "arc", "remotive", "remoteok", "indeed",
                     "glassdoor", "linkedin", "hn_hiring", "kuhustle", "zindi"]:
        applier = get_applier(board_id)
        assert applier is not None
        assert hasattr(applier, "apply"), f"{board_id} applier missing apply()"


def test_get_applier_unknown_board_returns_redirect():
    """Unknown board falls back to RedirectApplier, not an error."""
    applier = get_applier("some_future_board_xyz")
    assert isinstance(applier, RedirectApplier)


def test_registry_board_ids_match_class_board_id():
    """Each applier in the registry has the correct board_id attribute."""
    for board_id, applier in APPLIER_REGISTRY.items():
        assert applier.board_id == board_id, (
            f"APPLIER_REGISTRY['{board_id}'].board_id = '{applier.board_id}'"
        )


# ── No-apply boards return skipped ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_linkedin_applier_skips():
    r = await LinkedInApplier().apply("https://linkedin.com/jobs/apply/123", {}, None, None)
    assert r.skipped is True
    assert r.success is False


@pytest.mark.asyncio
async def test_hn_hiring_applier_skips():
    r = await HNHiringApplier().apply("https://news.ycombinator.com/item?id=123", {}, None, None)
    assert r.skipped is True


@pytest.mark.asyncio
async def test_kuhustle_applier_skips():
    r = await KuhusteApplier().apply("https://kuhustle.com/job/123", {}, None, None)
    assert r.skipped is True


@pytest.mark.asyncio
async def test_zindi_applier_skips():
    r = await ZindiApplier().apply("https://zindi.africa/competitions/123", {}, None, None)
    assert r.skipped is True


# ── URL-to-ATS detection ──────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected_ats", [
    ("https://boards.greenhouse.io/stripe/jobs/12345",    "greenhouse"),
    ("https://job-boards.greenhouse.io/openai/jobs/99",   "greenhouse"),
    ("https://jobs.lever.co/atlassian/abc-123",           "lever"),
    ("https://lever.co/netflix/abc",                      "lever"),
    ("https://jobs.ashbyhq.com/cursor/xyz",               "ashby"),
    ("https://myworkdayjobs.com/microsoft/",              "workday"),
    ("https://careers.somecompany.com/apply/123",         "universal"),
    ("https://remotive.com/job/123",                      "universal"),
])
def test_detect_ats_from_url(url, expected_ats):
    assert _detect_ats_from_url(url) == expected_ats


# ── auto_apply field on board registry ───────────────────────────────────────

def test_full_auto_apply_boards_have_dedicated_appliers():
    """Boards tagged auto_apply='full' must have a non-redirect dedicated applier."""
    from app.services.job_hunter.board_registry import all_boards
    full_boards = [b for b in all_boards() if b.auto_apply == "full"]
    assert len(full_boards) > 0, "Expected at least some full auto-apply boards"
    for board in full_boards:
        applier = get_applier(board.id)
        assert not isinstance(applier, RedirectApplier), (
            f"{board.id} is tagged auto_apply='full' but uses RedirectApplier"
        )


def test_none_auto_apply_boards_skip():
    """Boards tagged auto_apply='none' must return skipped=True without a browser."""
    import asyncio
    from app.services.job_hunter.board_registry import all_boards
    none_boards = [b for b in all_boards() if b.auto_apply == "none"]
    for board in none_boards:
        applier = get_applier(board.id)
        result = asyncio.run(applier.apply("https://example.com", {}, None, None))
        assert result.skipped is True, (
            f"{board.id} is tagged auto_apply='none' but did not return skipped=True"
        )
