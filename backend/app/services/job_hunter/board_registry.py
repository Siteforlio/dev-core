# backend/app/services/job_hunter/board_registry.py
"""
Static registry of every job board the system can scrape.

Each entry declares what the board covers so the dispatcher can filter
boards without running anything. No imports from other app modules here —
this file must be importable with zero side-effects for use in tests.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

CompanyType = Literal["faang", "enterprise", "startup", "sme", "all"]
WorkType    = Literal["remote", "hybrid", "onsite", "any"]
Region      = Literal["global", "africa", "kenya"]
AutoApply   = Literal["full", "partial", "none"]

@dataclass(frozen=True)
class BoardSpec:
    id: str                          # unique snake_case key
    display_name: str
    regions: tuple[Region, ...]      # which regions this board covers
    company_types: tuple[CompanyType, ...]  # relevant company categories
    work_types: tuple[WorkType, ...]  # work arrangements available on this board
    is_static: bool = False          # static = snapshot, only fetched once per run (ATS boards)
    avg_yield: int = 50              # expected jobs per call, used for target estimation
    priority: int = 5                # 1 (highest) … 10 (lowest) — dispatcher orders by this
    auto_apply: AutoApply = "none"   # full=every job auto-applicable, partial=best-effort, none=skip


# ── Registry ─────────────────────────────────────────────────────────────────

_BOARDS: list[BoardSpec] = [
    # ── JobSpy / public boards ─────────────────────────────────────────────
    BoardSpec(
        id="indeed",
        display_name="Indeed",
        regions=("global",),
        company_types=("faang", "enterprise", "startup", "sme", "all"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=80,
        priority=2,
        auto_apply="partial",   # external links redirect to company ATS
    ),
    BoardSpec(
        id="glassdoor",
        display_name="Glassdoor",
        regions=("global",),
        company_types=("faang", "enterprise", "startup", "sme", "all"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=60,
        priority=3,
        auto_apply="partial",
    ),
    BoardSpec(
        id="zip_recruiter",
        display_name="ZipRecruiter",
        regions=("global",),
        company_types=("enterprise", "sme", "all"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=50,
        priority=4,
        auto_apply="partial",   # external links go to company ATS; ZipRecruiter 1-click needs account
    ),
    BoardSpec(
        id="google",
        display_name="Google Jobs",
        regions=("global",),
        company_types=("faang", "enterprise", "startup", "sme", "all"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=70,
        priority=2,
        auto_apply="partial",   # aggregator — redirects to company career page
    ),
    # ── ATS company boards (static — snapshot per run) ─────────────────────
    BoardSpec(
        id="greenhouse",
        display_name="Greenhouse ATS",
        regions=("global",),
        company_types=("faang", "startup", "enterprise"),
        work_types=("remote", "hybrid", "onsite", "any"),
        is_static=True,
        avg_yield=200,
        priority=1,
        auto_apply="partial",   # prefills all fields, leaves submit to user (reCAPTCHA guard)
    ),
    BoardSpec(
        id="lever",
        display_name="Lever ATS",
        regions=("global",),
        company_types=("startup", "enterprise"),
        work_types=("remote", "hybrid", "onsite", "any"),
        is_static=True,
        avg_yield=100,
        priority=1,
        auto_apply="full",      # every URL is jobs.lever.co — dedicated filler exists
    ),
    BoardSpec(
        id="ashby",
        display_name="Ashby ATS",
        regions=("global",),
        company_types=("startup",),
        work_types=("remote", "hybrid", "onsite", "any"),
        is_static=True,
        avg_yield=80,
        priority=1,
        auto_apply="full",      # every URL is jobs.ashbyhq.com — dedicated filler exists
    ),
    # ── Startup / remote boards ────────────────────────────────────────────
    BoardSpec(
        id="wellfound",
        display_name="Wellfound",
        regions=("global",),
        company_types=("startup", "faang", "sme"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=80,
        priority=1,        # highest priority — best startup coverage globally
        auto_apply="partial",
    ),
    BoardSpec(
        id="remotive",
        display_name="Remotive",
        regions=("global",),
        company_types=("startup", "sme"),
        work_types=("remote",),
        avg_yield=60,
        priority=2,
        auto_apply="partial",   # links to company career pages — ATS hit rate ~60%
    ),
    BoardSpec(
        id="remoteok",
        display_name="RemoteOK",
        regions=("global",),
        company_types=("startup", "sme"),
        work_types=("remote",),
        avg_yield=50,
        priority=2,
        auto_apply="partial",
    ),
    BoardSpec(
        id="hn_hiring",
        display_name="HN Who's Hiring",
        regions=("global",),
        company_types=("startup",),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=40,
        priority=2,
        auto_apply="none",      # mostly email addresses or bare career page URLs — not automatable
    ),
    BoardSpec(
        id="weworkremotely",
        display_name="We Work Remotely",
        regions=("global",),
        company_types=("startup", "sme"),
        work_types=("remote",),
        avg_yield=40,
        priority=3,
        auto_apply="partial",
    ),
    BoardSpec(
        id="zindi",
        display_name="Zindi Africa",
        regions=("africa",),
        company_types=("startup", "sme"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=20,
        priority=4,
        auto_apply="none",      # competition platform — no standard apply form
    ),
    BoardSpec(
        id="startupdeals_africa",
        display_name="Startup Deals Africa",
        regions=("africa",),
        company_types=("startup",),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=15,
        priority=4,
        auto_apply="partial",   # links to company pages — variable quality
    ),
    # ── Kenya / Africa boards ──────────────────────────────────────────────
    BoardSpec(
        id="brightermonday",
        display_name="BrighterMonday",
        regions=("kenya",),
        company_types=("enterprise", "sme", "all"),
        work_types=("hybrid", "onsite", "any"),
        is_static=True,
        avg_yield=40,
        priority=3,
        auto_apply="full",      # consistent apply form — dedicated filler
    ),
    BoardSpec(
        id="myjobmag",
        display_name="MyJobMag Kenya",
        regions=("kenya",),
        company_types=("sme", "all"),
        work_types=("hybrid", "onsite", "any"),
        is_static=True,
        avg_yield=25,
        priority=4,
        auto_apply="partial",   # some jobs have inline forms, others redirect
    ),
    BoardSpec(
        id="kuhustle",
        display_name="Kuhustle",
        regions=("kenya",),
        company_types=("startup", "sme"),
        work_types=("remote", "hybrid", "any"),
        is_static=True,
        avg_yield=15,
        priority=5,
        auto_apply="none",      # freelance gig platform — no standard job application flow
    ),
    BoardSpec(
        id="andela",
        display_name="Andela",
        regions=("africa",),
        company_types=("startup", "enterprise"),
        work_types=("remote", "hybrid", "any"),
        is_static=True,
        avg_yield=20,
        priority=3,
        auto_apply="full",      # talent network with consistent apply form — dedicated filler
    ),
    BoardSpec(
        id="arc",
        display_name="Arc.dev",
        regions=("africa", "global"),
        company_types=("startup", "sme"),
        work_types=("remote",),
        is_static=True,
        avg_yield=25,
        priority=3,
        auto_apply="full",      # consistent profile-based apply — dedicated filler
    ),
    # ── LinkedIn (optional — requires credentials) ─────────────────────────
    BoardSpec(
        id="linkedin",
        display_name="LinkedIn",
        regions=("global",),
        company_types=("faang", "enterprise", "startup", "sme", "all"),
        work_types=("remote", "hybrid", "onsite", "any"),
        avg_yield=100,
        priority=1,
        auto_apply="none",      # LinkedIn Easy Apply needs dedicated browser session — explicitly skipped
    ),
]

# Index by id for O(1) lookup
_INDEX: dict[str, BoardSpec] = {b.id: b for b in _BOARDS}


# ── Public API ────────────────────────────────────────────────────────────────

def get_board(board_id: str) -> BoardSpec:
    """Return a BoardSpec by id. Raises KeyError if not found."""
    return _INDEX[board_id]


def all_boards() -> list[BoardSpec]:
    """All registered boards, priority-sorted (lowest number = highest priority)."""
    return sorted(_BOARDS, key=lambda b: b.priority)


def select_boards(
    *,
    company_types: list[CompanyType] | None = None,
    work_type: WorkType = "any",
    regions: list[Region] | None = None,
    require_linkedin: bool = False,
) -> list[BoardSpec]:
    """
    Filter boards to those relevant for the given campaign preferences.

    Rules:
    - If regions is None or empty, all regions are allowed (anywhere mode).
    - If company_types is None or empty, all company types are allowed.
    - work_type filters boards that don't carry that work arrangement at all.
    - LinkedIn is excluded unless require_linkedin=True (needs credentials).
    - Returns boards sorted by priority ascending (best first).
    """
    results: list[BoardSpec] = []

    for board in _BOARDS:
        # Skip LinkedIn unless caller explicitly opts in
        if board.id == "linkedin" and not require_linkedin:
            continue

        # Region filter — if regions specified, board must cover at least one
        if regions:
            if not any(r in board.regions for r in regions):
                continue

        # Company type filter — when a filter is active the board must explicitly
        # list at least one of the requested types. "all" alone doesn't qualify;
        # it only means the board is general-purpose when NO filter is applied.
        if company_types:
            if not any(ct in board.company_types for ct in company_types):
                continue

        # Work type filter — only exclude if the board explicitly can't serve it
        if work_type != "any":
            if work_type not in board.work_types and "any" not in board.work_types:
                continue

        results.append(board)

    return sorted(results, key=lambda b: b.priority)


def estimate_rounds_needed(
    selected: list[BoardSpec],
    daily_target: int,
) -> int:
    """
    Rough estimate of how many dispatcher rounds are needed to hit the target.
    Uses avg_yield of dynamic boards only (static boards only run once).
    Minimum 1 round.
    """
    static_yield  = sum(b.avg_yield for b in selected if b.is_static)
    dynamic_yield = sum(b.avg_yield for b in selected if not b.is_static)
    if static_yield >= daily_target:
        return 1
    remaining = daily_target - static_yield
    if dynamic_yield == 0:
        return 1
    import math
    return max(1, math.ceil(remaining / dynamic_yield))
