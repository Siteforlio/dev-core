# backend/tests/integration/test_all_scrapers_live.py
"""
Live integration test — hits every job board one-by-one and prints 5 raw listings.

No AI endpoints are called. No DB, Redis, or Celery needed.
Each board runs sequentially so output is readable per-board.

Run:
    cd backend
    source venv/Scripts/activate          # Windows
    python tests/integration/test_all_scrapers_live.py

Or with pytest (slow, requires internet):
    pytest tests/integration/test_all_scrapers_live.py -s -v --timeout=600

Boards tested (26 total):
  ATS (no auth)         : greenhouse (3 slugs), lever (3 slugs), ashby (3 slugs)
  Startup / remote      : remotive, remoteok, weworkremotely, hn_hiring, wellfound
  Africa / Kenya        : myjobmag, kuhustle, zindi, startupdeals_africa
  Global (no auth)      : the_muse, jobicy, himalayas, getonboard
  Global (API key opt.) : adzuna, reed
  JobSpy aggregators    : indeed, glassdoor   (skipped if jobspy not installed)

  Skipped (need browser/AI/creds):
    brightermonday, andela, arc  — nodriver browser
    fuzu                         — Vertex AI browser-use agent
    linkedin                     — requires credentials
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime

# Windows: ProactorEventLoop required for nodriver subprocess usage elsewhere
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Make app importable when run as a script from the backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import httpx

# ── Scraper imports ────────────────────────────────────────────────────────────
from app.services.job_hunter.ats_scrapers import (
    GREENHOUSE_SLUGS, LEVER_SLUGS, ASHBY_SLUGS,
    scrape_greenhouse, scrape_lever, scrape_ashby,
)
from app.services.job_hunter.startup_scrapers import (
    scrape_remotive,
    scrape_remoteok,
    scrape_weworkremotely,
    scrape_hn_who_is_hiring,
    scrape_wellfound,
    scrape_zindi,
    scrape_startupdeals_africa,
)
from app.services.job_hunter.kenya_scrapers import (
    scrape_myjobmag,
    scrape_kuhustle,
)
from app.services.job_hunter.global_scrapers import (
    scrape_the_muse,
    scrape_jobicy,
    scrape_himalayas,
    scrape_getonboard,
    scrape_adzuna,
    scrape_reed,
)

# ── Config ────────────────────────────────────────────────────────────────────
SEARCH_TERM   = "software engineer"   # used for boards that accept a keyword
PER_BOARD     = 5                     # raw listings to show per board
SEP           = "-" * 72
SEP2          = "=" * 72

# Representative slugs used for ATS per-board tests (not the full list)
_GH_TEST_SLUGS = ["anthropic", "stripe", "notion"]
_LV_TEST_SLUGS = ["netflix", "spotify", "mistral"]
_AB_TEST_SLUGS = ["elevenlabs", "n8n", "supabase"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _fmt_job(job: dict, idx: int) -> str:
    title   = (job.get("title")   or "").strip()[:55]
    company = (job.get("company") or "").strip()[:30]
    loc     = (job.get("location") or "")[:22]
    remote  = "remote" if job.get("remote") else "      "
    url     = (job.get("apply_url") or job.get("url") or "")[:80]
    source  = (job.get("source") or "")
    return (
        f"  {idx:>2}. [{source:<18}] {title:<55}  {company:<30}  {loc:<22}  {remote}\n"
        f"      -> {url}"
    )


def _print_board_result(
    name: str,
    jobs: list[dict],
    elapsed: float,
    note: str = "",
) -> None:
    count  = len(jobs)
    status = "✅" if count > 0 else "⚠️ "
    print(f"\n{SEP}")
    print(f"  {status}  {name:<24}  {count:>3} listings  ({elapsed:.1f}s){f'  [{note}]' if note else ''}")
    print(SEP)
    for i, job in enumerate(jobs[:PER_BOARD], 1):
        print(_fmt_job(job, i))
    if count == 0:
        print("    -- no listings returned (site may be blocked or empty)")


# ── Individual board test functions ───────────────────────────────────────────

async def test_greenhouse(client: httpx.AsyncClient) -> tuple[str, list[dict], float, str]:
    t0 = time.monotonic()
    results = await asyncio.gather(
        *[scrape_greenhouse(slug, client) for slug in _GH_TEST_SLUGS],
        return_exceptions=True,
    )
    jobs: list[dict] = []
    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
    return "greenhouse", jobs, time.monotonic() - t0, f"slugs: {_GH_TEST_SLUGS}"


async def test_lever(client: httpx.AsyncClient) -> tuple[str, list[dict], float, str]:
    t0 = time.monotonic()
    results = await asyncio.gather(
        *[scrape_lever(slug, client) for slug in _LV_TEST_SLUGS],
        return_exceptions=True,
    )
    jobs: list[dict] = []
    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
    return "lever", jobs, time.monotonic() - t0, f"slugs: {_LV_TEST_SLUGS}"


async def test_ashby(client: httpx.AsyncClient) -> tuple[str, list[dict], float, str]:
    t0 = time.monotonic()
    results = await asyncio.gather(
        *[scrape_ashby(slug, client) for slug in _AB_TEST_SLUGS],
        return_exceptions=True,
    )
    jobs: list[dict] = []
    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
    return "ashby", jobs, time.monotonic() - t0, f"slugs: {_AB_TEST_SLUGS}"


async def _simple(name: str, fn, client: httpx.AsyncClient, **kw) -> tuple[str, list[dict], float, str]:
    t0 = time.monotonic()
    try:
        jobs = await fn(SEARCH_TERM, client, **kw)
    except Exception as e:
        jobs = []
        _log(f"  [{name}] error: {e}")
    return name, jobs, time.monotonic() - t0, ""


async def test_jobspy_board(name: str, client: httpx.AsyncClient) -> tuple[str, list[dict], float, str]:
    """Test a jobspy-backed board (indeed / glassdoor). Skips if jobspy not installed."""
    t0 = time.monotonic()
    try:
        from jobspy import scrape_jobs
        import asyncio as _asyncio
        df = await _asyncio.to_thread(
            scrape_jobs,
            site_name=[name],
            search_term=SEARCH_TERM,
            results_wanted=10,
            hours_old=72,
        )
        jobs: list[dict] = []
        if not df.empty:
            for _, row in df.iterrows():
                jobs.append({
                    "source":   name,
                    "title":    str(row.get("title") or ""),
                    "company":  str(row.get("company") or ""),
                    "location": str(row.get("location") or ""),
                    "remote":   str(row.get("is_remote", "")).lower() == "true",
                    "url":      str(row.get("job_url") or ""),
                    "apply_url": str(row.get("job_url_direct") or row.get("job_url") or ""),
                    "description": str(row.get("description") or ""),
                })
        return name, jobs, time.monotonic() - t0, "jobspy"
    except ImportError:
        return name, [], time.monotonic() - t0, "SKIPPED — jobspy not installed"
    except Exception as e:
        return name, [], time.monotonic() - t0, f"error: {e}"


# ── Board manifest ─────────────────────────────────────────────────────────────
# Each entry: (display_name, coroutine_factory)
# The factory receives a single argument: the shared httpx.AsyncClient

async def _run_all(client: httpx.AsyncClient) -> list[tuple[str, list[dict], float, str]]:
    results = []

    _log("Testing ATS boards (Greenhouse, Lever, Ashby)...")
    results.append(await test_greenhouse(client))
    results.append(await test_lever(client))
    results.append(await test_ashby(client))

    _log("Testing startup / remote boards...")
    for name, fn in [
        ("remotive",            scrape_remotive),
        ("remoteok",            scrape_remoteok),
        ("weworkremotely",      scrape_weworkremotely),
        ("hn_hiring",           scrape_hn_who_is_hiring),
        ("wellfound",           scrape_wellfound),
        ("zindi",               scrape_zindi),
        ("startupdeals_africa", scrape_startupdeals_africa),
    ]:
        results.append(await _simple(name, fn, client))

    _log("Testing Kenya / Africa boards (HTTP-only)...")
    for name, fn in [
        ("myjobmag",  scrape_myjobmag),
        ("kuhustle",  scrape_kuhustle),
    ]:
        results.append(await _simple(name, fn, client))

    _log("Testing new global boards (no auth)...")
    for name, fn in [
        ("the_muse",   scrape_the_muse),
        ("jobicy",     scrape_jobicy),
        ("himalayas",  scrape_himalayas),
        ("getonboard", scrape_getonboard),
    ]:
        results.append(await _simple(name, fn, client))

    _log("Testing optional API-key boards (Adzuna, Reed)...")
    results.append(await _simple("adzuna", scrape_adzuna, client))
    results.append(await _simple("reed",   scrape_reed,   client))

    _log("Testing JobSpy aggregators (Indeed, Glassdoor)...")
    results.append(await test_jobspy_board("indeed",    client))
    results.append(await test_jobspy_board("glassdoor", client))

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> list[tuple[str, list[dict], float, str]]:
    print(SEP2)
    print("  LIVE SCRAPER TEST — ALL BOARDS  (5 raw listings per board, no AI)")
    print(f"  Search term: '{SEARCH_TERM}'  |  Started: {_ts()}")
    print(SEP2)

    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        results = await _run_all(client)

    # ── Print all results ──
    for name, jobs, elapsed, note in results:
        _print_board_result(name, jobs, elapsed, note)

    # ── Summary table ──
    print(f"\n{SEP2}")
    print("  SUMMARY")
    print(SEP2)
    print(f"  {'Board':<24}  {'Jobs':>5}  {'Time':>6}  Notes")
    print(f"  {'-'*24}  {'-'*5}  {'-'*6}  {'-'*30}")

    passed = 0
    failed = []
    for name, jobs, elapsed, note in results:
        status = "✅" if len(jobs) > 0 else "⚠️ "
        note_short = note[:40] if note else ""
        print(f"  {status}  {name:<22}  {len(jobs):>5}  {elapsed:>5.1f}s  {note_short}")
        if len(jobs) > 0:
            passed += 1
        else:
            failed.append(name)

    print(SEP2)
    print(f"  {passed}/{len(results)} boards returned results")
    if failed:
        print(f"  Boards with 0 results: {', '.join(failed)}")
    print(SEP2)

    return results


# ── Pytest entry point ────────────────────────────────────────────────────────

import pytest

@pytest.mark.asyncio
@pytest.mark.timeout(600)
async def test_all_scrapers_live():
    """
    Live integration test — each no-auth board should return at least some listings.
    API-key boards (adzuna, reed) and jobspy boards are not asserted on since
    they require optional setup.
    """
    NO_ASSERT = {
        "adzuna", "reed",       # optional API keys
        "indeed", "glassdoor",  # jobspy may not be installed
    }

    results = await main()
    failed = [
        name for name, jobs, _, _ in results
        if name not in NO_ASSERT and len(jobs) == 0
    ]
    assert not failed, f"These boards returned 0 listings: {failed}"


# ── Direct run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main())
