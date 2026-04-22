# backend/tests/services/test_board_registry.py
import pytest
from app.services.job_hunter.board_registry import (
    all_boards, get_board, select_boards, estimate_rounds_needed,
)


def test_all_boards_returns_sorted_by_priority():
    boards = all_boards()
    assert len(boards) > 0
    priorities = [b.priority for b in boards]
    assert priorities == sorted(priorities)


def test_get_board_known():
    b = get_board("indeed")
    assert b.id == "indeed"
    assert b.display_name == "Indeed"


def test_get_board_unknown_raises():
    with pytest.raises(KeyError):
        get_board("nonexistent_board_xyz")


def test_select_boards_excludes_linkedin_by_default():
    boards = select_boards()
    assert all(b.id != "linkedin" for b in boards)


def test_select_boards_includes_linkedin_when_requested():
    boards = select_boards(require_linkedin=True)
    assert any(b.id == "linkedin" for b in boards)


def test_select_boards_kenya_region():
    boards = select_boards(regions=["kenya"])
    ids = {b.id for b in boards}
    # Kenya boards should be present
    assert "fuzu" in ids
    assert "brightermonday" in ids
    # Global-only boards should be absent
    assert "indeed" not in ids
    assert "glassdoor" not in ids


def test_select_boards_global_region():
    boards = select_boards(regions=["global"])
    ids = {b.id for b in boards}
    assert "indeed" in ids
    assert "glassdoor" in ids
    # Kenya-only boards should not appear
    assert "fuzu" not in ids
    assert "brightermonday" not in ids


def test_select_boards_no_region_returns_all():
    boards_none = select_boards(regions=None)
    boards_empty = select_boards(regions=[])
    # Both should behave as "anywhere" and include both global and kenya
    ids_none = {b.id for b in boards_none}
    ids_empty = {b.id for b in boards_empty}
    assert ids_none == ids_empty
    assert "indeed" in ids_none
    assert "fuzu" in ids_none


def test_select_boards_startup_company_type():
    boards = select_boards(company_types=["startup"])
    ids = {b.id for b in boards}
    # Startup-tagged boards
    assert "remotive" in ids
    assert "hn_hiring" in ids
    assert "ashby" in ids
    # ZipRecruiter is enterprise/sme — should be absent
    assert "zip_recruiter" not in ids


def test_select_boards_faang_company_type():
    boards = select_boards(company_types=["faang"])
    ids = {b.id for b in boards}
    assert "greenhouse" in ids
    assert "indeed" in ids
    # remoteok is startup/sme only — should be absent
    assert "remoteok" not in ids


def test_select_boards_remote_work_type():
    boards = select_boards(work_type="remote")
    # Boards that only have onsite/hybrid should be excluded
    for b in boards:
        assert "remote" in b.work_types or "any" in b.work_types, (
            f"{b.id} has work_types={b.work_types} but was included for remote"
        )


def test_select_boards_result_is_priority_sorted():
    boards = select_boards()
    priorities = [b.priority for b in boards]
    assert priorities == sorted(priorities)


def test_estimate_rounds_needed_static_covers_target():
    # If static boards alone cover the target, 1 round is enough
    boards = select_boards(regions=["global"])
    # greenhouse avg_yield=200, lever=100, ashby=80 → 380 static yield
    rounds = estimate_rounds_needed(boards, daily_target=300)
    assert rounds == 1


def test_estimate_rounds_needed_multiple_rounds():
    # Only dynamic boards with low yield → multiple rounds needed
    boards = [b for b in all_boards() if not b.is_static and b.id != "linkedin"]
    # Each dynamic board yields ~40-80. Sum should be < 1000 so rounds > 1 at target=1000
    rounds = estimate_rounds_needed(boards, daily_target=10000)
    assert rounds > 1
