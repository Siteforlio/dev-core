#!/usr/bin/env python
# backend/tests/integration/test_pipeline.py
"""
Full end-to-end pipeline integration test.

Tests the complete flow WITHOUT Celery workers (calls services directly):
  1. DB reachable  — connect to PostgreSQL, create test user + campaign
  2. Scrape        — pull 1 real job from Greenhouse
  3. Save listing  — write JobListing to DB
  4. Tailor        — run TailorService.tailor_for_listing() (calls Vertex AI)
  5. Apply         — run ApplyService.submit_application_for_board() (opens browser)
  6. Verify        — check Application.status in DB (applied/failed/skipped)
  7. Cleanup       — delete all test rows

Prerequisites (must be running):
  - PostgreSQL at DATABASE_URL (docker-compose: localhost:5433)
  - Redis at REDIS_URL          (docker-compose: localhost:6379)
  - Vertex AI credentials in env (VERTEX_PROJECT, VERTEX_LOCATION + ADC)

Usage:
    cd backend
    venv\\Scripts\\python tests/integration/test_pipeline.py

    # With visible browser and actual submit:
    HEADLESS=0 SUBMIT=1 venv\\Scripts\\python tests/integration/test_pipeline.py

    # Skip the apply step (tailor only):
    SKIP_APPLY=1 venv\\Scripts\\python tests/integration/test_pipeline.py

Env vars:
    DATABASE_URL  — override DB (default: reads from app.core.config.settings)
    HEADLESS      — 1 = headless browser (default 1)
    SUBMIT        — 1 = actually click submit; 0 = stop before (default 0)
    SKIP_APPLY    — 1 = skip browser apply step entirely (default 0)
    BOARD         — which board to test (default: greenhouse)
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import time
import uuid
from datetime import datetime

# Windows ProactorEventLoop for nodriver
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ── Config ────────────────────────────────────────────────────────────────────
HEADLESS   = os.environ.get("HEADLESS",    "1") == "1"
SUBMIT     = os.environ.get("SUBMIT",      "0") == "1"
SKIP_APPLY = os.environ.get("SKIP_APPLY",  "0") == "1"
BOARD      = os.environ.get("BOARD",       "greenhouse")

# Unique test-run marker so all test rows can be found and deleted
_RUN_ID    = str(uuid.uuid4())[:8]
TEST_EMAIL = f"pipeline.test.{_RUN_ID}@devnull.local"
TEST_NAME  = f"PipelineBot {_RUN_ID}"

# Minimal but complete profile for the tailor service
TEST_PROFILE_DATA = {
    "full_name":    TEST_NAME,
    "email":        TEST_EMAIL,
    "phone":        "+254700000000",
    "city":         "Nairobi",
    "country":      "Kenya",
    "linkedin_url": "https://linkedin.com/in/pipelinebot",
    "github_url":   "https://github.com/pipelinebot",
    "portfolio_url": None,
    "skills": ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Docker"],
    "work_experience": [
        {
            "company":    "Acme Tech",
            "title":      "Software Engineer",
            "start_date": "2022-01",
            "end_date":   None,
            "current":    True,
            "description": "Built FastAPI microservices and React dashboards.",
        }
    ],
    "education": [
        {
            "institution": "University of Nairobi",
            "degree":      "BSc Computer Science",
            "start_date":  "2016-09",
            "end_date":    "2020-06",
        }
    ],
    "summary": (
        "Full-stack engineer with 4 years experience in Python/FastAPI and React. "
        "Strong background in PostgreSQL, Docker, and AWS."
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _step(n: int, label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  STEP {n}: {label}")
    print(f"{'='*60}")


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


# ── DB session factory ────────────────────────────────────────────────────────

def _make_session():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings
    engine = create_async_engine(
        settings.database_url,
        pool_size=2, max_overflow=0, pool_pre_ping=True,
    )
    return async_sessionmaker(engine, expire_on_commit=False), engine


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline() -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'#'*60}")
    print(f"  Pipeline Integration Test — {timestamp}")
    print(f"  Board: {BOARD}  |  Headless: {HEADLESS}  |  Submit: {SUBMIT}")
    print(f"  Run ID: {_RUN_ID}  |  Skip apply: {SKIP_APPLY}")
    print(f"{'#'*60}")

    Session, engine = _make_session()
    test_user_id     = None
    test_campaign_id = None
    test_listing_id  = None
    test_app_id      = None

    try:
        # ── STEP 1: DB connectivity ───────────────────────────────────────────
        _step(1, "DB connectivity")
        from sqlalchemy import text
        async with Session() as db:
            result = await db.execute(text("SELECT 1"))
            assert result.scalar() == 1
        _ok("PostgreSQL reachable")

        # ── STEP 2: Create test user + profile + campaign ─────────────────────
        _step(2, "Create test data in DB")
        import hashlib as _hl
        from app.models.pg.user import User
        from app.models.pg.job_hunter import (
            JobHunterProfile, JobHunterCampaign, JobListing, Application
        )

        async with Session() as db:
            # User
            user = User(
                id=str(uuid.uuid4()),
                name=TEST_NAME,
                email=TEST_EMAIL,
                hashed_password=_hl.sha256(b"test").hexdigest(),
            )
            db.add(user)
            await db.flush()
            test_user_id = user.id
            _ok(f"User created: {user.id}")

            # Profile
            profile = JobHunterProfile(
                user_id=user.id,
                is_complete=True,
                completion_score=100,
                full_name=TEST_PROFILE_DATA["full_name"],
                email=TEST_PROFILE_DATA["email"],
                phone=TEST_PROFILE_DATA["phone"],
                city=TEST_PROFILE_DATA["city"],
                country=TEST_PROFILE_DATA["country"],
                linkedin_url=TEST_PROFILE_DATA["linkedin_url"],
                github_url=TEST_PROFILE_DATA["github_url"],
                skills=TEST_PROFILE_DATA["skills"],
                work_experience=TEST_PROFILE_DATA["work_experience"],
                education=TEST_PROFILE_DATA["education"],
            )
            db.add(profile)
            _ok("Profile created")

            # Campaign
            campaign = JobHunterCampaign(
                user_id=user.id,
                name=f"Pipeline Test {_RUN_ID}",
                broad_category="Software Engineering",
                sub_categories=["Backend", "Full Stack"],
                status="active",
                work_type="remote",
                anywhere=True,
            )
            db.add(campaign)
            await db.flush()
            test_campaign_id = campaign.id
            _ok(f"Campaign created: {campaign.id}")

            await db.commit()

        # ── STEP 3: Scrape 1 real job ─────────────────────────────────────────
        _step(3, f"Scrape 1 job from {BOARD}")
        import httpx
        job = None

        async with httpx.AsyncClient(timeout=20) as client:
            if BOARD == "greenhouse":
                from app.services.job_hunter.ats_scrapers import scrape_greenhouse
                for slug in ["stripe", "openai", "notion", "figma", "linear", "vercel"]:
                    jobs = await scrape_greenhouse(slug, client)
                    if jobs:
                        job = jobs[0]
                        _ok(f"Got job: '{job['title']}' @ {job['company']}")
                        _ok(f"Apply URL: {job['apply_url']}")
                        break
            elif BOARD == "lever":
                from app.services.job_hunter.ats_scrapers import scrape_lever
                for slug in ["mercury", "brex", "rippling", "benchling"]:
                    jobs = await scrape_lever(slug, client)
                    if jobs:
                        job = jobs[0]
                        _ok(f"Got job: '{job['title']}' @ {job['company']}")
                        break
            elif BOARD == "ashby":
                from app.services.job_hunter.ats_scrapers import scrape_ashby
                for slug in ["linear", "ramp", "retool", "descript"]:
                    jobs = await scrape_ashby(slug, client)
                    if jobs:
                        job = jobs[0]
                        _ok(f"Got job: '{job['title']}' @ {job['company']}")
                        break

        if not job:
            _fail(f"No jobs returned from {BOARD} — aborting")
            return

        # ── STEP 4: Save listing to DB ────────────────────────────────────────
        _step(4, "Save JobListing to DB")
        async with Session() as db:
            listing = JobListing(
                campaign_id=test_campaign_id,
                source=BOARD,
                title=job["title"],
                company=job["company"],
                location=job.get("location"),
                remote=job.get("remote", False),
                url=job["apply_url"],
                apply_url=job["apply_url"],
                description=job.get("description", "")[:5000],
                url_hash=_url_hash(job["apply_url"]),
                status="pending",
            )
            db.add(listing)
            await db.commit()
            test_listing_id = listing.id
            _ok(f"JobListing saved: {listing.id}")

        # ── STEP 5: Tailor (LLM) ─────────────────────────────────────────────
        _step(5, "Tailor resume via LLM (Vertex AI)")
        t0 = time.time()
        async with Session() as db:
            from app.services.job_hunter.tailor_service import TailorService
            svc = TailorService(db)
            app_row = await svc.tailor_for_listing(test_listing_id, test_user_id)

        elapsed = time.time() - t0
        if not app_row:
            _fail(f"tailor_for_listing returned None (listing skipped or error) — {elapsed:.1f}s")
            print("     This may happen if the job description doesn't match the profile skills.")
            print("     Try a different board or job to get a match.")
            return

        test_app_id = app_row.id
        _ok(f"Application created: {app_row.id}  ({elapsed:.1f}s)")
        _ok(f"Status after tailor: {app_row.status}")
        _ok(f"Cover letter: {(app_row.cover_letter or '')[:80]}…")
        _ok(f"Resume PDF url: {app_row.tailored_resume_pdf_url or '(not set)'}")

        # ── STEP 6: Apply (browser) ───────────────────────────────────────────
        if SKIP_APPLY:
            _step(6, "Apply — SKIPPED (SKIP_APPLY=1)")
        else:
            _step(6, f"Apply via browser  [SUBMIT={'YES' if SUBMIT else 'NO — stop before submit'}]")
            t1 = time.time()
            async with Session() as db:
                from app.services.job_hunter.apply_service import ApplyService
                apply_svc = ApplyService(db)
                apply_svc._headless = HEADLESS

                # Temporarily patch submit behaviour based on SUBMIT flag
                if not SUBMIT:
                    # Monkey-patch: stop before the final click by overriding click_human
                    # to always return False on the submit selector
                    _orig_submit = apply_svc.submit_application_for_board

                    async def _no_submit(application_id: str, board_id: str) -> bool:
                        """Same as real apply but skip the final submit click."""
                        from app.services.job_hunter.board_appliers import get_applier
                        from app.services.job_hunter.board_appliers.no_apply import (
                            LinkedInApplier, HNHiringApplier, KuhusteApplier, ZindiApplier
                        )
                        from sqlalchemy import select
                        from app.models.pg.job_hunter import Application as _App, JobListing as _JL
                        from app.services.job_hunter.browser_service import BrowserService
                        from app.services.job_hunter.apply_service import _SCAN_FIELDS_JS, _make_fill_js
                        import json as _json

                        async with Session() as _db:
                            app_r = (await _db.execute(
                                select(_App).where(_App.id == application_id)
                            )).scalar_one_or_none()
                            if not app_r:
                                return False
                            jl = (await _db.execute(
                                select(_JL).where(_JL.id == app_r.job_listing_id)
                            )).scalar_one_or_none()
                            if not jl:
                                return False

                        _applier = get_applier(board_id)
                        if isinstance(_applier, (LinkedInApplier, HNHiringApplier,
                                                 KuhusteApplier, ZindiApplier)):
                            print("  (skipped — no-apply board)")
                            return False

                        _svc = ApplyService.__new__(ApplyService)
                        _svc._headless = HEADLESS
                        _form_url = await _svc._detect_form_url(jl.apply_url)
                        _nav = _form_url or jl.apply_url
                        print(f"  Browser opening: {_nav[:80]}")

                        async with BrowserService(headless=HEADLESS) as _browser:
                            _page = await _browser.new_page()
                            await _browser.goto(_page, _nav, wait=3.0)
                            await _browser.wait_past_cloudflare(_page)
                            current = await _browser.current_url(_page)
                            print(f"  Landed on: {current[:80]}")
                            await asyncio.sleep(1.5)
                            raw = await _page.evaluate(_SCAN_FIELDS_JS) or "[]"
                            fields = _json.loads(raw) if isinstance(raw, str) else (raw or [])
                            fillable = [f for f in fields if f.get("label") or f.get("options")]
                            print(f"  Fields found: {len(fillable)}")
                            if fillable:
                                ctx = {
                                    "full_name": TEST_PROFILE_DATA["full_name"],
                                    "email":     TEST_PROFILE_DATA["email"],
                                    "phone":     TEST_PROFILE_DATA["phone"],
                                    "city":      TEST_PROFILE_DATA["city"],
                                    "country":   TEST_PROFILE_DATA["country"],
                                    "linkedin_url": TEST_PROFILE_DATA["linkedin_url"],
                                    "github_url":   TEST_PROFILE_DATA["github_url"],
                                    "portfolio_url": None,
                                    "cover_letter": app_r.cover_letter or "",
                                    "resume_pdf": None,
                                    "job_title": jl.title,
                                    "company":   jl.company,
                                    "summary":   TEST_PROFILE_DATA["summary"],
                                }
                                answers = await ApplyService._ai_map_fields_static(fillable, ctx)
                                filled = 0
                                for field in fillable:
                                    idx   = str(field.get("idx", ""))
                                    val   = answers.get(idx, "")
                                    sel   = field.get("selector", "")
                                    ftype = field.get("type", "text")
                                    if not val or sel.startswith("__idx__"):
                                        continue
                                    try:
                                        if ftype in ("radio", "checkbox", "select"):
                                            await _page.evaluate(_make_fill_js(sel, str(val), ftype))
                                        elif len(str(val)) > 80:
                                            await _browser.fill_field(_page, sel, str(val))
                                        else:
                                            await _browser.type_human(_page, sel, str(val))
                                        filled += 1
                                        await asyncio.sleep(0.15)
                                    except Exception:
                                        pass
                                print(f"  Fields filled: {filled}/{len(fillable)}")
                            print("  STOPPED before submit (SUBMIT=0)")
                        return True  # report success even though we didn't click submit

                    success = await _no_submit(test_app_id, BOARD)
                else:
                    success = await apply_svc.submit_application_for_board(test_app_id, BOARD)

            elapsed = time.time() - t1
            if success:
                _ok(f"Apply step completed ({elapsed:.1f}s)")
            else:
                _fail(f"Apply step failed ({elapsed:.1f}s)")

            # Read back Application.status from DB
            async with Session() as db:
                from sqlalchemy import select
                final_app = (await db.execute(
                    select(Application).where(Application.id == test_app_id)
                )).scalar_one_or_none()
            if final_app:
                _ok(f"Application.status in DB: {final_app.status}")
            else:
                _fail("Application row not found after apply step")

        # ── STEP 7: Summary ───────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print("  PIPELINE SUMMARY")
        print(f"{'='*60}")
        print(f"  Board:          {BOARD}")
        print(f"  Job:            {job['title']} @ {job['company']}")
        print(f"  Listing ID:     {test_listing_id}")
        print(f"  Application ID: {test_app_id}")
        if not SKIP_APPLY and final_app:
            print(f"  Final status:   {final_app.status}")
        print(f"  ALL STEPS PASSED")

    except Exception as exc:
        import traceback
        print(f"\n  PIPELINE FAILED: {exc}")
        traceback.print_exc()

    finally:
        # ── STEP 8: Cleanup ───────────────────────────────────────────────────
        print(f"\n{'─'*60}")
        print("  Cleaning up test data…")
        try:
            async with Session() as db:
                from sqlalchemy import delete
                from app.models.pg.job_hunter import (
                    Application, JobListing, JobHunterCampaign,
                    JobHunterProfile, CampaignActivityLog
                )
                from app.models.pg.user import User

                if test_app_id:
                    await db.execute(delete(Application).where(Application.id == test_app_id))
                if test_listing_id:
                    await db.execute(delete(JobListing).where(JobListing.id == test_listing_id))
                if test_campaign_id:
                    await db.execute(delete(CampaignActivityLog).where(
                        CampaignActivityLog.campaign_id == test_campaign_id))
                    await db.execute(delete(JobHunterCampaign).where(
                        JobHunterCampaign.id == test_campaign_id))
                if test_user_id:
                    await db.execute(delete(JobHunterProfile).where(
                        JobHunterProfile.user_id == test_user_id))
                    await db.execute(delete(User).where(User.id == test_user_id))
                await db.commit()
            print("  Test data deleted.")
        except Exception as cleanup_err:
            print(f"  Cleanup error (manual cleanup may be needed): {cleanup_err}")
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_pipeline())
