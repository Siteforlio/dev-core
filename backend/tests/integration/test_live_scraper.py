# backend/tests/integration/test_live_scraper.py
"""
Live integration test -- hits every real job board and runs until 100 tech jobs found.

Run:
    cd backend
    source venv/Scripts/activate
    python tests/integration/test_live_scraper.py

Or with pytest (slow, requires internet):
    pytest tests/integration/test_live_scraper.py -s -v --timeout=600
"""
import asyncio
import sys
import os
from collections import defaultdict
from datetime import datetime

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make sure app is importable when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.services.job_hunter.startup_scrapers import scrape_all_startup_boards
from app.services.job_hunter.kenya_scrapers import scrape_all_kenya_boards
from app.services.job_hunter.scraper_service import (
    _smb_score,
    _STARTUP_NATIVE_SOURCES,
    _TECH_REJECT_SIGNALS,
    _TECH_ACCEPT_SIGNALS,
)
import re as _re


def _tech_role_prefilter(title: str, description: str) -> bool:
    t = title.lower()
    if any(sig in t for sig in _TECH_REJECT_SIGNALS):
        return False
    if any(sig in t for sig in _TECH_ACCEPT_SIGNALS):
        return True
    stripped = _re.sub(r'<[^>]+>', ' ', description).lower()[:300]
    if any(sig in stripped for sig in _TECH_ACCEPT_SIGNALS):
        return True
    return True


TARGET = 100

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
]

SEP = "-" * 72


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _print_job(job: dict, idx: int) -> None:
    source  = job.get("source", "?")
    title   = (job.get("title") or "").strip()[:55]
    company = (job.get("company") or "").strip()[:35]
    location = (job.get("location") or "-")[:25]
    remote  = "remote" if job.get("remote") else location
    smb_tag = "[startup]" if _smb_score(job) >= 2 else ""
    print(
        f"  {idx:>3}. [{source:<20}] {title:<55}  {company:<35}  {remote:<25}  {smb_tag}",
        flush=True,
    )


async def _publish(msg: str) -> None:
    _log(msg)


async def run_pass(search_term: str) -> list[dict]:
    _log(f"Scraping '{search_term}' across all boards...")

    startup_jobs, kenya_jobs = await asyncio.gather(
        scrape_all_startup_boards(search_term, publish_fn=_publish),
        scrape_all_kenya_boards(search_term, publish_fn=_publish),
    )

    all_jobs = startup_jobs + kenya_jobs
    _log(f"  Raw total: {len(all_jobs)} listings ({len(startup_jobs)} startup + {len(kenya_jobs)} kenya)")
    return all_jobs


async def main() -> list[dict]:
    print(SEP)
    print("  LIVE JOB BOARD INTEGRATION TEST")
    print(f"  Target: {TARGET} tech jobs  |  Boards: startup (6) + kenya (6) = 12 total")
    print(SEP)

    tech_jobs: list[dict] = []
    seen_keys: set[str] = set()
    per_source: dict[str, int] = defaultdict(int)
    skipped_non_tech = 0
    pass_num = 0

    while len(tech_jobs) < TARGET:
        search_term = SEARCH_TERMS[pass_num % len(SEARCH_TERMS)]
        pass_num += 1

        print(f"\n{SEP}")
        _log(f"Pass {pass_num} -- {len(tech_jobs)}/{TARGET} tech jobs found so far")
        print(SEP)

        raw = await run_pass(search_term)

        new_this_pass = 0
        for job in raw:
            key = f"{(job.get('company') or '').lower().strip()}|{(job.get('title') or '').lower().strip()}"
            if not key.strip("|") or key in seen_keys:
                continue
            seen_keys.add(key)

            if not _tech_role_prefilter(job.get("title", ""), job.get("description", "")):
                skipped_non_tech += 1
                continue

            tech_jobs.append(job)
            per_source[job.get("source", "unknown")] += 1
            new_this_pass += 1
            _print_job(job, len(tech_jobs))

            if len(tech_jobs) >= TARGET:
                break

        _log(f"Pass {pass_num} done -- {new_this_pass} new tech jobs (total {len(tech_jobs)}/{TARGET})")

        if len(tech_jobs) < TARGET and new_this_pass == 0:
            _log("  No new results -- waiting 30s before next pass...")
            await asyncio.sleep(30)

    print(f"\n{SEP}")
    print(f"  DONE -- {len(tech_jobs)} tech jobs  |  {skipped_non_tech} non-tech filtered")
    print(SEP)
    print("\n  Results by source:")
    for source, count in sorted(per_source.items(), key=lambda x: -x[1]):
        tag = "*" if source in _STARTUP_NATIVE_SOURCES else " "
        print(f"    {tag} {source:<25}  {count:>4} jobs")
    print(f"\n  Total unique tech jobs: {len(tech_jobs)}")
    print(SEP)

    return tech_jobs


# -- Pytest entry point -------------------------------------------------------
import pytest

@pytest.mark.asyncio
@pytest.mark.timeout(600)
async def test_live_scraper_reaches_100_tech_jobs():
    """
    Live integration test -- actually hits all 12 job boards.
    Passes when >= 100 unique tech jobs are collected.
    Run explicitly with: pytest tests/integration/ -s -v
    """
    jobs = await main()
    assert len(jobs) >= TARGET, f"Only collected {len(jobs)}, expected {TARGET}"


# -- Direct run entry point ---------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
