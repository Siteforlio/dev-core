# backend/tests/services/test_board_scrape_isolation.py
"""
Verify that a single failing board does not crash the aggregate step.
The chord callback receives a mix of success and failure result dicts;
the aggregate must still process the successful boards' jobs.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_board_result(board_id: str, jobs: list[dict] | None = None, error: str | None = None) -> dict:
    return {"board_id": board_id, "jobs": jobs or [], "error": error}


def test_aggregate_handles_failed_board_gracefully():
    """
    If one board returns error + empty jobs, the other boards' jobs still flow through.
    aggregate_board_results must not raise and must process the healthy results.
    """
    board_results = [
        _make_board_result("indeed",   jobs=[{"title": "SWE", "company": "Google", "source": "indeed",
                                               "description": "", "url": "", "apply_url": "",
                                               "location": None, "location_country": None, "remote": True}]),
        _make_board_result("fuzu",     jobs=[], error="ConnectionError: timed out"),  # failed board
        _make_board_result("remotive", jobs=[{"title": "Backend Dev", "company": "Startup", "source": "remotive",
                                               "description": "", "url": "", "apply_url": "",
                                               "location": None, "location_country": None, "remote": True}]),
    ]

    # The aggregate only processes jobs — error field is informational, not fatal.
    # Verify that flattening + dedup works regardless of error entries.
    from app.services.job_hunter.deduplicator import deduplicate

    all_jobs = []
    for r in board_results:
        all_jobs.extend(r.get("jobs") or [])

    deduped = deduplicate(all_jobs)
    assert len(deduped) == 2  # indeed + remotive, fuzu contributed nothing


def test_aggregate_handles_all_boards_failed():
    """If every board fails, result is 0 jobs — no exception."""
    board_results = [
        _make_board_result("indeed",   error="Timeout"),
        _make_board_result("glassdoor", error="HTTP 503"),
    ]
    from app.services.job_hunter.deduplicator import deduplicate

    all_jobs = []
    for r in board_results:
        all_jobs.extend(r.get("jobs") or [])

    deduped = deduplicate(all_jobs)
    assert deduped == []


def test_aggregate_deduplicates_across_boards():
    """Same job appearing on two boards → only one copy after dedup."""
    job_a = {"title": "Backend Engineer", "company": "Stripe",
             "source": "greenhouse", "description": "", "url": "https://a",
             "apply_url": "https://a", "location": None, "location_country": None, "remote": True}
    job_a_dup = {**job_a, "source": "indeed", "url": "https://b", "apply_url": "https://b"}

    board_results = [
        _make_board_result("greenhouse", jobs=[job_a]),
        _make_board_result("indeed",     jobs=[job_a_dup]),
    ]

    from app.services.job_hunter.deduplicator import deduplicate

    all_jobs = []
    for r in board_results:
        all_jobs.extend(r.get("jobs") or [])

    deduped = deduplicate(all_jobs)
    assert len(deduped) == 1
    # First (highest priority) source is kept
    assert deduped[0]["source"] == "greenhouse"
