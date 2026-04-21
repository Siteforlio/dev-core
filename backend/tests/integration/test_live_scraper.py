# backend/tests/integration/test_live_scraper.py
"""
Live integration test -- hits every real job board with a per-board quota.
Each of the 12 boards is expected to deliver PER_BOARD_TARGET tech jobs.
Boards are run in parallel; boards that haven't hit quota get retried with
rotating search terms until they have or have exhausted all terms.

Run:
    cd backend
    source venv/Scripts/activate
    python tests/integration/test_live_scraper.py

Or with pytest (slow, requires internet):
    pytest tests/integration/test_live_scraper.py -s -v --timeout=900
"""
import asyncio
import sys
import os
import httpx
from collections import defaultdict
from datetime import datetime

# Windows: ProactorEventLoop is required for nodriver (Chrome subprocess)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Force UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make app importable when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.services.job_hunter.startup_scrapers import (
    scrape_remotive,
    scrape_remoteok,
    scrape_hn_who_is_hiring,
    scrape_weworkremotely,
    scrape_zindi,
    scrape_startupdeals_africa,
)
from app.services.job_hunter.kenya_scrapers import (
    scrape_fuzu,
    scrape_brightermonday,
    scrape_myjobmag,
    scrape_kuhustle,
    scrape_andela,
    scrape_arc,
)
from app.services.job_hunter.scraper_service import (
    _smb_score,
    _STARTUP_NATIVE_SOURCES,
    _TECH_REJECT_SIGNALS,
    _TECH_ACCEPT_SIGNALS,
)
import re as _re

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PER_BOARD_TARGET = 10   # jobs to collect per board; total = 12 * 10 = 120

SEARCH_TERMS = [
    "software engineer",
    "backend developer",
    "data engineer",
    "frontend developer",
    "full stack developer",
    "python developer",
    "product manager",
    "devops engineer",
    "machine learning engineer",
    "mobile developer",
    "cloud engineer",
    "qa engineer",
]

# Boards that need a browser open their own browser internally.
# Fuzu uses headless=False — Cloudflare Turnstile auto-solves for visible Chrome.
BOARDS = [
    # name              scraper fn              uses_nodriver
    ("remotive",            scrape_remotive,            False),
    ("remoteok",            scrape_remoteok,            False),
    ("hn_hiring",           scrape_hn_who_is_hiring,    False),
    ("weworkremotely",      scrape_weworkremotely,      False),
    ("zindi",               scrape_zindi,               False),
    ("startupdeals_africa", scrape_startupdeals_africa, False),
    ("fuzu",                scrape_fuzu,                True),   # headless=False, CF auto-solves
    ("brightermonday",      scrape_brightermonday,      True),
    ("myjobmag",            scrape_myjobmag,            False),
    ("kuhustle",            scrape_kuhustle,            False),
    ("andela",              scrape_andela,              True),
    ("arc",                 scrape_arc,                 True),
]

SEP  = "-" * 80
SEP2 = "=" * 80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _is_tech(title: str, description: str) -> bool:
    t = title.lower()
    if any(s in t for s in _TECH_REJECT_SIGNALS):
        return False
    if any(s in t for s in _TECH_ACCEPT_SIGNALS):
        return True
    stripped = _re.sub(r"<[^>]+>", " ", description).lower()[:300]
    return any(s in stripped for s in _TECH_ACCEPT_SIGNALS)


def _fmt_job(job: dict, idx: int) -> str:
    title     = (job.get("title") or "").strip()[:50]
    company   = (job.get("company") or "").strip()[:30]
    loc       = "remote" if job.get("remote") else (job.get("location") or "-")[:18]
    apply_url = job.get("apply_url") or job.get("url") or ""
    tag       = "[startup]" if _smb_score(job) >= 2 else ""
    apply_tag = f"  -> {apply_url[:80]}" if apply_url else "  -> (no apply link)"
    return f"  {idx:>3}. {title:<50}  {company:<30}  {loc:<18}  {tag}\n{apply_tag}"


# ---------------------------------------------------------------------------
# Per-board scrape loop
# ---------------------------------------------------------------------------
async def scrape_board_to_quota(
    name: str,
    scraper_fn,
    quota: int,
    client: httpx.AsyncClient,
) -> list[dict]:
    """
    Call scraper_fn with rotating search terms until `quota` unique tech jobs
    are collected from this board, or all search terms are exhausted.
    Returns whatever was collected (may be < quota if board is blocked/empty).
    """
    collected: list[dict] = []
    seen: set[str] = set()
    term_idx = 0

    while len(collected) < quota and term_idx < len(SEARCH_TERMS):
        term = SEARCH_TERMS[term_idx]
        term_idx += 1
        try:
            raw = await scraper_fn(term, client)
        except Exception as e:
            _log(f"  [{name}] error on '{term}': {e}")
            raw = []

        before = len(collected)
        for job in raw:
            key = f"{(job.get('company') or '').lower().strip()}|{(job.get('title') or '').lower().strip()}"
            if not key.strip("|") or key in seen:
                continue
            seen.add(key)
            if not _is_tech(job.get("title", ""), job.get("description", "")):
                continue
            job["source"] = name
            collected.append(job)
            if len(collected) >= quota:
                break
        added = len(collected) - before
        _log(f"  [{name}] term='{term}' raw={len(raw)} +{added} total={len(collected)}/{quota}")

        # If we got results but zero were new, this board always returns the same page
        # (e.g. Fuzu maps all tech terms to the same category URL) — no point retrying
        if raw and added == 0 and len(collected) > 0:
            _log(f"  [{name}] all results were duplicates — stopping early")
            break

    return collected


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> dict[str, list[dict]]:
    print(SEP2)
    print("  LIVE JOB BOARD INTEGRATION TEST  --  PER-BOARD QUOTA")
    print(f"  {len(BOARDS)} boards  x  {PER_BOARD_TARGET} jobs each  =  {len(BOARDS) * PER_BOARD_TARGET} target total")
    print(SEP2)

    # One shared httpx client (browser-based scrapers ignore it but signature requires it)
    async with httpx.AsyncClient(follow_redirects=True) as client:

        # All 12 boards run fully in parallel — each browser board opens its own Chrome
        _log(f"Running all {len(BOARDS)} boards in parallel...")
        all_results = await asyncio.gather(
            *[scrape_board_to_quota(n, f, PER_BOARD_TARGET, client) for n, f, _ in BOARDS]
        )
        results: dict[str, list[dict]] = dict(zip([n for n, _, _ in BOARDS], all_results))

    # ---------------------------------------------------------------------------
    # Print results
    # ---------------------------------------------------------------------------
    print()
    print(SEP2)
    print("  RESULTS BY BOARD")
    print(SEP2)

    grand_total = 0
    for name, fn, is_browser in BOARDS:
        jobs = results[name]
        grand_total += len(jobs)
        browser_tag = "(browser)" if is_browser else "(httpx) "
        status = f"{len(jobs):>3} / {PER_BOARD_TARGET}"
        print(f"\n  {name:<22} {browser_tag}  {status}")
        print(f"  {SEP}")
        for i, job in enumerate(jobs, 1):
            print(_fmt_job(job, i))
        if not jobs:
            print(f"    -- 0 results")

    print()
    print(SEP2)
    print("  SUMMARY")
    print(SEP2)
    print(f"  {'Board':<22}  {'Type':<10}  {'Collected':>9}  {'Target':>6}")
    print(f"  {'-'*22}  {'-'*10}  {'-'*9}  {'-'*6}")
    for name, fn, is_browser in BOARDS:
        jobs = results[name]
        t = "browser" if is_browser else "httpx"
        bar = "#" * len(jobs) + "." * max(0, PER_BOARD_TARGET - len(jobs))
        bar = bar[:PER_BOARD_TARGET]
        print(f"  {name:<22}  {t:<10}  {len(jobs):>9}  {PER_BOARD_TARGET:>6}  [{bar}]")
    print(f"\n  Grand total: {grand_total} tech jobs across {len(BOARDS)} boards")
    print(SEP2)

    return results


# ---------------------------------------------------------------------------
# Pytest entry point
# ---------------------------------------------------------------------------
import pytest

@pytest.mark.asyncio
@pytest.mark.timeout(900)
async def test_live_scraper_per_board_quota():
    """
    Live integration test -- each board should return at least some jobs.
    Boards with known blocks (fuzu) are excluded from assertions.
    Run explicitly: pytest tests/integration/ -s -v
    """
    KNOWN_BLOCKED: set[str] = set()

    results = await main()

    failed = []
    for name, _, _ in BOARDS:
        if name in KNOWN_BLOCKED:
            continue
        if len(results[name]) == 0:
            failed.append(name)

    assert not failed, f"These boards returned 0 jobs: {failed}"


# ---------------------------------------------------------------------------
# Direct run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
