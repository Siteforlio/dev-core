# backend/app/workers/board_scrape_worker.py
"""
Per-board asyncio tasks + dispatcher.

Architecture
────────────
  dispatch_scrape(campaign_id, user_id, preferences)
      │
      ├─ selects boards via board_registry.select_boards()
      ├─ marks board status in in-memory cache
      └─ fires asyncio.gather([scrape_board(board_id, ...) for board in selected])
             │
             └─ aggregate_board_results(results, campaign_id, ...)
                    │
                    ├─ deduplicate across boards
                    ├─ score with BERT → Gemini gate
                    ├─ save listings to DB
                    └─ if matches_found < daily_target and dynamic boards remain:
                           task_runner.submit(dispatch_scrape(... dynamic_only=True, round=N+1))

Each scrape_board coroutine:
  - runs the board-specific async scraper
  - writes {status, count, error} to in-memory cache key board_status:{campaign_id}:{board_id}
  - returns {"board_id": ..., "jobs": [...], "error": None}

Cache keys
──────────
  board_status:{campaign_id}:{board_id}  →  dict {status, count, error, updated_at}
  scrape_run:{campaign_id}               →  dict {status, matches, round, started_at}
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Cache helpers ─────────────────────────────────────────────────────────────

async def _set_board_status(campaign_id: str, board_id: str, status: str, count: int = 0, error: str | None = None):
    try:
        from app.core.cache import cache_set
        key = f"board_status:{campaign_id}:{board_id}"
        await cache_set(key, {
            "status": status,
            "count": count,
            "error": error,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, ttl=86400)
    except Exception:
        pass  # cache status is best-effort — never block scraping


async def _get_all_board_statuses(campaign_id: str) -> dict[str, dict]:
    """Return {board_id: {status, count, error}} for all boards in a campaign run."""
    try:
        from app.core.cache import cache_get
        from app.services.job_hunter.board_registry import all_boards
        result = {}
        for board in all_boards():
            key = f"board_status:{campaign_id}:{board.id}"
            data = await cache_get(key)
            if data:
                result[board.id] = data
        return result
    except Exception:
        return {}


async def _set_run_status(campaign_id: str, status: str, matches: int = 0, round_: int = 1):
    try:
        from app.core.cache import cache_get, cache_set
        key = f"scrape_run:{campaign_id}"
        existing = await cache_get(key)
        started_at = datetime.now(timezone.utc).isoformat()
        if existing:
            started_at = existing.get("started_at", started_at)
        await cache_set(key, {
            "status": status,
            "matches": matches,
            "round": round_,
            "started_at": started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, ttl=86400)
    except Exception:
        pass


async def _publish_activity(campaign_id: str, message: str):
    """Publish a message to the campaign activity feed (same channel as ScraperService)."""
    try:
        from app.core.cache import cache_get, list_append
        # Use the in-memory list_append so ScraperService SSE polling can read it
        key = f"campaign:{campaign_id}:activity"
        await list_append(key, {
            "text": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


# ── Board router ──────────────────────────────────────────────────────────────

async def _run_board(board_id: str, search_term: str, linkedin_creds: dict | None = None) -> list[dict]:
    """
    Route board_id to the correct async scraper function.
    Always returns a list of raw job dicts — never raises.
    """
    import httpx
    from app.services.job_hunter import (
        ats_scrapers, startup_scrapers, kenya_scrapers,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if board_id == "greenhouse":
                return await ats_scrapers.scrape_all_ats(search_term, publish_fn=None)

            elif board_id == "lever":
                from app.services.job_hunter.ats_scrapers import LEVER_SLUGS, scrape_lever
                results = await asyncio.gather(
                    *[scrape_lever(slug, client) for slug in LEVER_SLUGS],
                    return_exceptions=True,
                )
                jobs = []
                for r in results:
                    if isinstance(r, list):
                        jobs.extend(r)
                return jobs

            elif board_id == "ashby":
                from app.services.job_hunter.ats_scrapers import ASHBY_SLUGS, scrape_ashby
                results = await asyncio.gather(
                    *[scrape_ashby(slug, client) for slug in ASHBY_SLUGS],
                    return_exceptions=True,
                )
                jobs = []
                for r in results:
                    if isinstance(r, list):
                        jobs.extend(r)
                return jobs

            elif board_id == "wellfound":
                return await startup_scrapers.scrape_wellfound(search_term, client)

            elif board_id == "remotive":
                return await startup_scrapers.scrape_remotive(search_term, client)

            elif board_id == "remoteok":
                return await startup_scrapers.scrape_remoteok(search_term, client)

            elif board_id == "hn_hiring":
                return await startup_scrapers.scrape_hn_who_is_hiring(search_term, client)

            elif board_id == "weworkremotely":
                return await startup_scrapers.scrape_weworkremotely(search_term, client)

            elif board_id == "zindi":
                return await startup_scrapers.scrape_zindi(search_term, client)

            elif board_id == "startupdeals_africa":
                return await startup_scrapers.scrape_startupdeals_africa(search_term, client)

            # ── Browser-automation boards (stashed — nodriver/Playwright required)
            # elif board_id == "fuzu":
            #     return await kenya_scrapers.scrape_fuzu(search_term, client)
            # elif board_id == "brightermonday":
            #     return await kenya_scrapers.scrape_brightermonday(search_term, client)
            # elif board_id == "andela":
            #     return await kenya_scrapers.scrape_andela(search_term, client)
            # elif board_id == "arc":
            #     return await kenya_scrapers.scrape_arc(search_term, client)

            elif board_id == "myjobmag":
                return await kenya_scrapers.scrape_myjobmag(search_term, client)

            elif board_id == "kuhustle":
                return await kenya_scrapers.scrape_kuhustle(search_term, client)

            # ── Global boards (no auth) ────────────────────────────────────
            elif board_id == "the_muse":
                from app.services.job_hunter.global_scrapers import scrape_the_muse
                return await scrape_the_muse(search_term, client)

            elif board_id == "jobicy":
                from app.services.job_hunter.global_scrapers import scrape_jobicy
                return await scrape_jobicy(search_term, client)

            elif board_id == "himalayas":
                from app.services.job_hunter.global_scrapers import scrape_himalayas
                return await scrape_himalayas(search_term, client)

            elif board_id == "getonboard":
                from app.services.job_hunter.global_scrapers import scrape_getonboard
                return await scrape_getonboard(search_term, client)

            # ── Global boards (optional API key) ──────────────────────────
            elif board_id == "adzuna":
                from app.services.job_hunter.global_scrapers import scrape_adzuna
                return await scrape_adzuna(search_term, client)

            elif board_id == "reed":
                from app.services.job_hunter.global_scrapers import scrape_reed
                return await scrape_reed(search_term, client)

            elif board_id in ("indeed", "glassdoor", "zip_recruiter", "google"):
                # JobSpy boards — each one is a site_name in jobspy
                from jobspy import scrape_jobs
                source_map = {
                    "zip_recruiter": "zip_recruiter",
                    "google": "google",
                    "indeed": "indeed",
                    "glassdoor": "glassdoor",
                }
                df = await asyncio.to_thread(
                    scrape_jobs,
                    site_name=[source_map[board_id]],
                    search_term=search_term,
                    results_wanted=100,
                    hours_old=48,
                )
                if df.empty:
                    return []
                jobs = []
                seen: set[str] = set()
                for _, row in df.iterrows():
                    apply_url = str(row.get("job_url_direct") or row.get("job_url") or "")
                    if "linkedin.com/jobs/apply" in apply_url:
                        continue
                    dedup_key = f"{str(row.get('company') or '').lower()}|{str(row.get('title') or '').lower()}"
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    jobs.append({
                        "source": board_id,
                        "title": str(row.get("title") or ""),
                        "company": str(row.get("company") or ""),
                        "location": str(row.get("location") or "") or None,
                        "location_country": (str(row.get("country") or "")[:2].upper()) or None,
                        "remote": str(row.get("is_remote", "")).lower() == "true",
                        "url": str(row.get("job_url") or ""),
                        "apply_url": apply_url,
                        "description": str(row.get("description") or ""),
                    })
                return jobs

            elif board_id == "linkedin":
                if not linkedin_creds:
                    return []
                from app.services.job_hunter.scraper_service import _run_linkedin_subprocess
                from app.services.job_hunter.linkedin_scraper import LinkedInScraper
                li = LinkedInScraper(
                    email=linkedin_creds.get("email"),
                    password=linkedin_creds.get("password"),
                    session_cookie=linkedin_creds.get("session_cookie"),
                )
                return await _run_linkedin_subprocess(li, search_term, None, "remote", None)

            else:
                logger.warning("board_scrape_worker: unknown board_id '%s'", board_id)
                return []

    except Exception as exc:
        logger.exception("_run_board %s failed", board_id)
        raise  # re-raise so scrape_board can record the error


# ── Async tasks ───────────────────────────────────────────────────────────────

async def scrape_board(
    board_id: str,
    campaign_id: str,
    search_term: str,
    linkedin_creds: dict | None = None,
) -> dict:
    """
    Scrape a single board and return raw jobs.

    Return shape: {"board_id": str, "jobs": list[dict], "error": str | None}
    """
    await _set_board_status(campaign_id, board_id, "running")
    await _publish_activity(campaign_id, f"🔄 [{board_id}] starting...")

    try:
        jobs = await _run_board(board_id, search_term, linkedin_creds)
        await _set_board_status(campaign_id, board_id, "done", count=len(jobs))
        await _publish_activity(campaign_id, f"✅ [{board_id}] {len(jobs)} listings fetched")
        return {"board_id": board_id, "jobs": jobs, "error": None}

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        await _set_board_status(campaign_id, board_id, "failed", error=err_msg)
        await _publish_activity(campaign_id, f"❌ [{board_id}] failed — {err_msg}")
        return {"board_id": board_id, "jobs": [], "error": err_msg}


async def aggregate_board_results(
    board_results: list[dict],
    campaign_id: str,
    user_id: str,
    preferences: dict,
    round_: int = 1,
) -> dict:
    """
    Receives results from all scrape_board coroutines (via asyncio.gather).

    Steps:
      1. Flatten all jobs from all boards
      2. Deduplicate across boards
      3. Apply work-type + location filters
      4. Score with BERT → Gemini gate
      5. Save to DB
      6. If matches < daily_target and dynamic boards remain → re-dispatch round N+1
    """
    from app.core.database import AsyncSessionLocal
    from app.services.job_hunter.deduplicator import deduplicate
    from app.services.job_hunter.board_registry import select_boards, get_board
    from app.services.job_hunter.scraper_service import ScraperService

    async with AsyncSessionLocal() as db:
        svc = ScraperService(db)
        svc._campaign_id = campaign_id

        daily_target   = preferences.get("daily_target", 100)
        # work_types takes priority over work_type for multi-select support
        work_type      = preferences.get("work_types") or preferences.get("work_type", "any")
        user_country   = preferences.get("user_country", "")
        anywhere       = preferences.get("anywhere", True)
        sub_categories = preferences.get("sub_categories", [])
        broad_category = preferences.get("search_term", "")
        profile_skills = preferences.get("profile_skills", [])
        search_term    = preferences.get("search_term", "")

        # ── 1. Flatten ────────────────────────────────────────────────
        total_raw = 0
        # Sort board results by board priority so dedup keeps the best source
        def _board_priority(r: dict) -> int:
            try:
                return get_board(r["board_id"]).priority
            except Exception:
                return 99

        sorted_results = sorted(board_results, key=_board_priority)
        all_jobs: list[dict] = []
        for result in sorted_results:
            jobs = result.get("jobs") or []
            total_raw += len(jobs)
            all_jobs.extend(jobs)

        await _publish_activity(campaign_id, f"📦 Round {round_}: {total_raw} raw listings from {len(board_results)} boards")

        # ── 2. Deduplicate across boards ──────────────────────────────
        deduped = deduplicate(all_jobs)
        dropped = total_raw - len(deduped)
        if dropped:
            await _publish_activity(campaign_id, f"🧹 Deduplicated: {dropped} duplicates removed → {len(deduped)} unique")

        # ── 3. Work-type + location filter ────────────────────────────
        filtered = [
            j for j in deduped
            if svc.passes_work_type_filter(j, work_type, user_country, anywhere)
        ]
        await _publish_activity(campaign_id, f"🗺️  Location filter: {len(filtered)}/{len(deduped)} passed")

        # ── 4. Category pre-filter ────────────────────────────────────
        tech_filtered = [
            j for j in filtered
            if svc._category_prefilter(
                j.get("title", ""), j.get("description", ""),
                broad_category, sub_categories,
            )
        ]

        # ── 5. Score (BERT gate → Gemini) and save ────────────────────
        from app.services.job_hunter.matcher_service import matcher

        matches_saved = 0
        for job in tech_filtered:
            # BERT pre-score — avoid Gemini on obvious mismatches
            if profile_skills:
                profile_text = " | ".join(profile_skills[:30])
                jd_text = f"{job.get('title', '')} {job.get('description', '')[:800]}"
                bert_score = matcher.score_fit(jd_text, profile_text)
            else:
                bert_score = 0.5  # no profile skills → let Gemini decide

            if bert_score >= 0.75:
                score = "MATCH"
            elif bert_score < 0.20:
                score = "SKIP"
            else:
                # Grey zone — call Gemini (cheap Flash Lite)
                score = await svc.score_job_match(
                    job.get("title", ""),
                    job.get("description", ""),
                    sub_categories,
                    profile_skills,
                )

            if score != "SKIP":
                await _publish_activity(
                    campaign_id,
                    f"{'✅' if score == 'MATCH' else '🟡'} {score} — {job.get('title')} @ {job.get('company')}",
                )

            listing = await svc.save_listing(campaign_id, user_id, job, score)
            if listing and score == "MATCH":
                matches_saved += 1

        await _publish_activity(
            campaign_id,
            f"💾 Round {round_} saved: {matches_saved} MATCH listings (target: {daily_target})"
        )
        await _set_run_status(campaign_id, "running" if matches_saved < daily_target else "done",
                        matches=matches_saved, round_=round_)

    daily_target = preferences.get("daily_target", 100)
    max_rounds   = preferences.get("max_rounds", 5)

    # ── 6. Re-dispatch dynamic boards if target not met ───────────────────
    if matches_saved < daily_target and round_ < max_rounds:
        await _publish_activity(
            campaign_id,
            f"🔁 Target {daily_target} not reached ({matches_saved} found) — launching round {round_ + 1}"
        )
        from app.core.task_runner import get_runner
        get_runner().submit(dispatch_scrape(
            campaign_id=campaign_id,
            user_id=user_id,
            preferences=preferences,
            dynamic_only=True,
            round_=round_ + 1,
        ))
    else:
        await _set_run_status(campaign_id, "done", matches=matches_saved, round_=round_)
        await _publish_activity(campaign_id, f"🏁 Scrape complete — {matches_saved} matches saved")

    return {"matches_saved": matches_saved, "round": round_}


async def dispatch_scrape(
    campaign_id: str,
    user_id: str,
    preferences: dict,
    dynamic_only: bool = False,
    round_: int = 1,
) -> dict:
    """
    Entry point — called by the API when the user presses Scrape.

    preferences dict:
      search_term:    str        — e.g. "software engineer"
      company_types:  list[str]  — ["startup", "faang"] or [] for all
      work_type:      str        — "remote" | "hybrid" | "onsite" | "any"
      regions:        list[str]  — ["kenya"] or [] for anywhere
      user_country:   str        — ISO-2 country code, e.g. "KE"
      anywhere:       bool       — True = no location restriction
      daily_target:   int        — max jobs to collect (default 100)
      max_rounds:     int        — max re-dispatch rounds (default 5)
      sub_categories: list[str]
      profile_skills: list[str]
      linkedin_creds: dict | None
    """
    from app.services.job_hunter.board_registry import select_boards

    company_types  = preferences.get("company_types") or []
    # For board selection, collapse multi work_types: if multiple chosen, use "any" to cast wide net
    raw_work_types = preferences.get("work_types") or [preferences.get("work_type", "any")]
    work_type_for_boards = raw_work_types[0] if len(raw_work_types) == 1 else "any"
    regions        = preferences.get("regions") or []
    search_term    = preferences.get("search_term", "")
    linkedin_creds = preferences.get("linkedin_creds")

    selected = select_boards(
        company_types=company_types or None,
        work_type=work_type_for_boards,
        regions=regions or None,
        require_linkedin=bool(linkedin_creds),
    )

    # On re-dispatch rounds, skip static boards (they don't change)
    if dynamic_only:
        selected = [b for b in selected if not b.is_static]

    if not selected:
        await _publish_activity(campaign_id, "⚠️ No boards selected for this campaign configuration")
        await _set_run_status(campaign_id, "done", round_=round_)
        return {"boards": 0}

    board_ids = [b.id for b in selected]
    await _publish_activity(
        campaign_id,
        f"🚀 Round {round_}: dispatching {len(board_ids)} boards in parallel: {', '.join(board_ids)}"
    )
    await _set_run_status(campaign_id, "running", round_=round_)

    # Mark all selected boards as queued
    for b in selected:
        await _set_board_status(campaign_id, b.id, "queued")

    # Run all boards concurrently, then aggregate
    board_results = await asyncio.gather(
        *[
            scrape_board(b.id, campaign_id, search_term, linkedin_creds)
            for b in selected
        ],
        return_exceptions=False,
    )

    return await aggregate_board_results(
        list(board_results),
        campaign_id=campaign_id,
        user_id=user_id,
        preferences=preferences,
        round_=round_,
    )
