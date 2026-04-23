#!/usr/bin/env python
# backend/tests/integration/test_board_apply.py
"""
Per-board apply integration test.

For each board in BOARDS_TO_TEST:
  1. Scrape 1-3 real jobs from the board
  2. Open the apply form in a VISIBLE browser (headless=False)
  3. Fill every field using the test profile + tailored resume
  4. Stop BEFORE clicking the final Submit button
  5. Take a screenshot of the filled form
  6. Write a pass/fail result to output/

Nothing is actually submitted — the test halts at the last step so you
can visually verify the form was filled correctly.

Output layout:
  apply_test_output/
    YYYY-MM-DD_HH-MM-SS/
      summary.md
      <board>_<company>_<title>/
        screenshot_filled.png
        form_fields.json
        result.json   {board, url, fields_found, fields_filled, stopped_before_submit, error}

Usage:
    cd backend
    venv\\Scripts\\python tests/integration/test_board_apply.py

    # Test specific boards only:
    venv\\Scripts\\python tests/integration/test_board_apply.py greenhouse lever ashby

    # Run headless (no visible browser):
    HEADLESS=1 venv\\Scripts\\python tests/integration/test_board_apply.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# Windows: ProactorEventLoop required for nodriver
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

HEADLESS     = os.environ.get("HEADLESS",     "0") == "1"
SUBMIT       = os.environ.get("SUBMIT",       "0") == "1"
USE_PROFILE  = os.environ.get("USE_PROFILE",  "0") == "1"  # use real Chrome profile (Google signed in)

# Which boards to test (override via CLI args)
ALL_BOARDS = [
    "greenhouse",
    "lever",
    "ashby",
    "remotive",
    "remoteok",
    "weworkremotely",
    "indeed",
    "glassdoor",
    "fuzu",
    "brightermonday",
    "andela",
    "arc",
]

JOBS_PER_BOARD   = 1   # scrape this many jobs per board, apply to the first one found
SEARCH_TERM      = "software engineer"
OUTPUT_DIR       = Path(__file__).parent.parent.parent.parent / "apply_test_output"

# Pause (seconds) on the filled form before taking screenshot and moving on.
# Increase to 30+ to visually inspect in non-headless mode.
FILLED_PAUSE_SECS = int(os.environ.get("FILLED_PAUSE", "5"))

# ─────────────────────────────────────────────────────────────────────────────
# TEST PROFILE — realistic fake data, safe to auto-fill forms with
# ─────────────────────────────────────────────────────────────────────────────

_RUN_TS = datetime.now().strftime("%m%d%H%M")

TEST_PROFILE = {
    "full_name":           "Alex Testuser",
    # Unique per run so boards don't reject as "already applied"
    "email":               f"alex.testuser.{_RUN_TS}@gmail.com",
    "phone":               "+254712345678",
    "city":                "Nairobi",
    "country":             "Kenya",
    "linkedin_url":        "https://linkedin.com/in/alex-testuser-dev",
    "github_url":          "https://github.com/alex-testuser-dev",
    "portfolio_url":       "https://alex-testuser.dev",
    "years_of_experience": 4,
    "skills":              "Python, FastAPI, React, TypeScript, PostgreSQL, Docker, AWS, Redis",
    "summary": (
        "Full-stack software engineer with 4 years of experience building "
        "scalable web applications. Specialise in Python backends (FastAPI, Django) "
        "and React frontends. Comfortable across the full delivery lifecycle — "
        "design, implementation, testing, and production ops."
    ),
    "cover_letter": (
        "I am excited to apply for this role. With 4 years of hands-on experience "
        "in full-stack development using Python and React, I am confident I can "
        "contribute meaningfully from day one. I thrive in fast-paced environments "
        "and enjoy working on products that solve real user problems. "
        "I look forward to discussing how my background aligns with your team's goals."
    ),
    "salary":              "80000",
    "job_title":           "Software Engineer",   # filled in per-job below
    "company":             "Test Company",         # filled in per-job below
    # Board-specific credentials (set via env vars — never hardcoded)
    "fuzu_password":       os.environ.get("FUZU_PASSWORD"),
    "bm_password":         os.environ.get("BM_PASSWORD"),
    "andela_password":     os.environ.get("ANDELA_PASSWORD"),
    # resume_pdf is generated below
    "resume_pdf":          None,
}

# ─────────────────────────────────────────────────────────────────────────────
# Resume PDF — generate a minimal one-page PDF for upload tests
# ─────────────────────────────────────────────────────────────────────────────

RESUME_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 11pt; margin: 40px; color: #111; }
  h1   { font-size: 16pt; margin-bottom: 4px; }
  h2   { font-size: 11pt; color: #444; border-bottom: 1px solid #ccc; margin-top: 18px; }
  .contact { font-size: 9pt; color: #555; margin-bottom: 12px; }
  ul   { margin: 4px 0; padding-left: 18px; }
  li   { margin-bottom: 3px; }
</style>
</head><body>
<h1>Alex Testuser</h1>
<div class="contact">
  alex.testuser.dev@gmail.com &nbsp;|&nbsp; +254 712 345 678 &nbsp;|&nbsp;
  Nairobi, Kenya &nbsp;|&nbsp;
  linkedin.com/in/alex-testuser-dev &nbsp;|&nbsp; github.com/alex-testuser-dev
</div>

<h2>Summary</h2>
<p>Full-stack software engineer with 4 years of experience building scalable web applications
using Python (FastAPI, Django) and React/TypeScript. Strong background in PostgreSQL,
Docker, Redis, and AWS. Passionate about clean code and user-centric products.</p>

<h2>Experience</h2>
<p><strong>Software Engineer</strong> — Acme Tech Ltd, Nairobi &nbsp; 2022 – Present</p>
<ul>
  <li>Led migration of monolithic Django app to FastAPI microservices, reducing p99 latency by 40%.</li>
  <li>Built real-time dashboard in React + WebSockets serving 10,000 daily active users.</li>
  <li>Designed PostgreSQL schema and query optimisations cutting report generation from 8s to 0.4s.</li>
</ul>
<p><strong>Junior Developer</strong> — StartupXY, Nairobi &nbsp; 2020 – 2022</p>
<ul>
  <li>Developed REST APIs in Python/Flask for a fintech platform processing $500k/month.</li>
  <li>Integrated third-party payment providers (M-Pesa, Stripe) with full test coverage.</li>
</ul>

<h2>Education</h2>
<p><strong>BSc Computer Science</strong> — University of Nairobi &nbsp; 2016 – 2020</p>

<h2>Skills</h2>
<p>Python · FastAPI · Django · React · TypeScript · PostgreSQL · Redis · Docker · AWS ·
Git · REST APIs · WebSockets · CI/CD</p>
</body></html>"""


def _generate_resume_pdf() -> Path:
    """Generate a one-page PDF from RESUME_HTML using Chrome CLI."""
    import subprocess, tempfile, shutil

    output_path = OUTPUT_DIR / "test_resume_alex_testuser.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        return output_path

    html_path = output_path.with_suffix(".html")
    html_path.write_text(RESUME_HTML, encoding="utf-8")

    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "google-chrome",
        "chromium",
    ]
    chrome = next((c for c in chrome_candidates if shutil.which(c) or Path(c).exists()), None)
    if not chrome:
        print("  ⚠️  Chrome not found — resume PDF not generated, file uploads will be skipped")
        return output_path  # return path even if missing; upload step handles gracefully

    try:
        subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--print-to-pdf={output_path}",
                str(html_path),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        print(f"  ✅ Resume PDF generated: {output_path}")
    except Exception as e:
        print(f"  ⚠️  PDF generation failed ({e}) — uploads will be skipped")

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Scrape helpers — get 1 real apply_url per board
# ─────────────────────────────────────────────────────────────────────────────

async def _get_jobs_for_board(board_id: str, n: int = JOBS_PER_BOARD) -> list[dict]:
    """Return up to n real job dicts from the board. Never raises."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if board_id == "greenhouse":
                from app.services.job_hunter.ats_scrapers import GREENHOUSE_SLUGS, scrape_greenhouse
                # Try a few well-known companies until we get results
                for slug in ["stripe", "openai", "notion", "figma", "linear"]:
                    jobs = await scrape_greenhouse(slug, client)
                    if jobs:
                        return jobs[:n]
                return []

            elif board_id == "lever":
                from app.services.job_hunter.ats_scrapers import scrape_lever
                for slug in [
                    "benchling", "verkada", "ramp", "brex", "mercury",
                    "scale-ai", "anduril", "flexport", "plaid", "gusto",
                ]:
                    jobs = await scrape_lever(slug, client)
                    if jobs:
                        return jobs[:n]
                return []

            elif board_id == "ashby":
                from app.services.job_hunter.ats_scrapers import scrape_ashby
                for slug in [
                    "linear", "ramp", "vercel", "rippling", "retool",
                    "brex", "notion", "cursor", "codeium", "warp",
                    "loom", "figma", "descript", "replit",
                ]:
                    jobs = await scrape_ashby(slug, client)
                    if jobs:
                        return jobs[:n]
                return []

            elif board_id == "remotive":
                from app.services.job_hunter.startup_scrapers import scrape_remotive
                return (await scrape_remotive(SEARCH_TERM, client))[:n]

            elif board_id == "remoteok":
                from app.services.job_hunter.startup_scrapers import scrape_remoteok
                return (await scrape_remoteok(SEARCH_TERM, client))[:n]

            elif board_id == "weworkremotely":
                from app.services.job_hunter.startup_scrapers import scrape_weworkremotely
                return (await scrape_weworkremotely(SEARCH_TERM, client))[:n]

            elif board_id == "indeed":
                # Use jobspy for Indeed
                import pandas as pd
                from jobspy import scrape_jobs
                df = await asyncio.to_thread(
                    scrape_jobs, site_name=["indeed"], search_term=SEARCH_TERM,
                    results_wanted=5, hours_old=48
                )
                if df.empty:
                    return []
                jobs = []
                for _, row in df.iterrows():
                    url = str(row.get("job_url_direct") or row.get("job_url") or "")
                    if "linkedin" in url:
                        continue
                    jobs.append({
                        "source": "indeed",
                        "title": str(row.get("title") or ""),
                        "company": str(row.get("company") or ""),
                        "apply_url": url,
                        "url": str(row.get("job_url") or ""),
                    })
                    if len(jobs) >= n:
                        break
                return jobs

            elif board_id == "glassdoor":
                import pandas as pd
                from jobspy import scrape_jobs
                df = await asyncio.to_thread(
                    scrape_jobs, site_name=["glassdoor"], search_term=SEARCH_TERM,
                    results_wanted=5, hours_old=48
                )
                if df.empty:
                    return []
                jobs = []
                for _, row in df.iterrows():
                    url = str(row.get("job_url_direct") or row.get("job_url") or "")
                    jobs.append({
                        "source": "glassdoor",
                        "title": str(row.get("title") or ""),
                        "company": str(row.get("company") or ""),
                        "apply_url": url,
                        "url": url,
                    })
                    if len(jobs) >= n:
                        break
                return jobs

            elif board_id == "fuzu":
                from app.services.job_hunter.kenya_scrapers import scrape_fuzu
                return (await scrape_fuzu(SEARCH_TERM, client))[:n]

            elif board_id == "brightermonday":
                from app.services.job_hunter.kenya_scrapers import scrape_brightermonday
                return (await scrape_brightermonday(SEARCH_TERM, client))[:n]

            elif board_id == "andela":
                from app.services.job_hunter.kenya_scrapers import scrape_andela
                return (await scrape_andela(SEARCH_TERM, client))[:n]

            elif board_id == "arc":
                from app.services.job_hunter.kenya_scrapers import scrape_arc
                return (await scrape_arc(SEARCH_TERM, client))[:n]

            else:
                print(f"  ⚠️  No scraper defined for board '{board_id}' in this test")
                return []

    except Exception as exc:
        print(f"  ❌ Failed to scrape {board_id}: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Apply test — fill form, stop before submit, screenshot
# ─────────────────────────────────────────────────────────────────────────────

async def _test_apply_board(
    board_id: str,
    job: dict,
    ctx: dict,
    run_dir: Path,
) -> dict:
    """
    Open the apply form, fill it, stop before submitting.
    Returns a result dict.
    """
    from app.services.job_hunter.browser_service import BrowserService
    from app.services.job_hunter.apply_service import ApplyService, _SCAN_FIELDS_JS

    apply_url = job.get("apply_url") or job.get("url", "")
    title     = job.get("title", "unknown")
    company   = job.get("company", "unknown")

    safe_name = re.sub(r"[^\w\-]", "_", f"{board_id}_{company}_{title}")[:60]
    job_dir   = run_dir / safe_name
    job_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "board":               board_id,
        "company":             company,
        "title":               title,
        "url":                 apply_url,
        "fields_found":        0,
        "fields_filled":       0,
        "stopped_before_submit": False,
        "submitted":           False,
        "submit_success":      None,   # True/False/None (None = not attempted)
        "screenshot":          None,
        "screenshot_after":    None,
        "error":               None,
    }

    if not apply_url:
        result["error"] = "no apply_url"
        return result

    # Check if this board is no-apply
    from app.services.job_hunter.board_appliers import get_applier
    from app.services.job_hunter.board_appliers.no_apply import (
        LinkedInApplier, HNHiringApplier, KuhusteApplier, ZindiApplier
    )
    applier = get_applier(board_id)
    if isinstance(applier, (LinkedInApplier, HNHiringApplier, KuhusteApplier, ZindiApplier)):
        result["error"] = f"board {board_id} does not support auto-apply (skipped by design)"
        result["stopped_before_submit"] = True
        return result

    print(f"\n  🌐 Opening: {apply_url[:90]}")

    svc = ApplyService.__new__(ApplyService)
    svc._headless = HEADLESS

    try:
        # Resolve form URL before browser opens (same as real apply flow)
        form_url = await svc._detect_form_url(apply_url)
        navigate_to = form_url or apply_url
        if form_url:
            print(f"  🔀 Resolved to form URL: {form_url[:90]}")

        async with BrowserService(headless=HEADLESS, use_profile=USE_PROFILE) as browser:
            page = await browser.new_page()
            await browser.goto(page, navigate_to, wait=3.0)
            await browser.wait_past_cloudflare(page)

            # ── Detect board-specific or redirect landing ──────────────────
            current_url = await browser.current_url(page)
            print(f"  📄 Landed on: {current_url[:90]}")

            # ── If redirect board: follow to company page ─────────────────
            from app.services.job_hunter.board_appliers.redirect_apply import (
                RedirectApplier, _detect_ats_from_url, _board_own_domains, _find_external_apply_link
            )
            if isinstance(applier, RedirectApplier):
                board_domains = _board_own_domains(board_id)
                if board_domains and any(d in current_url for d in board_domains):
                    ext_link = await _find_external_apply_link(page, board_domains)
                    if ext_link:
                        print(f"  🔗 Following external link: {ext_link[:90]}")
                        await browser.goto(page, ext_link, wait=3.0)
                        current_url = await browser.current_url(page)
                        print(f"  📄 Company page: {current_url[:90]}")

            # ── Upload resume FIRST so autofill fires before field scan ──────
            import json as _json
            resume_uploaded = False
            if ctx.get("resume_pdf") and Path(ctx["resume_pdf"]).exists():
                try:
                    await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                    resume_uploaded = True
                    print("  📎 Resume uploaded early (triggers autofill)")
                    await asyncio.sleep(4.0)  # wait for autofill to complete
                except Exception:
                    pass

            # ── Wait for form fields to appear (React SPAs render async) ─────
            for _ in range(20):
                await asyncio.sleep(0.5)
                cnt = await page.evaluate(
                    "document.querySelectorAll("
                    "'input:not([type=hidden]):not([disabled]),"
                    "select:not([disabled]),textarea:not([disabled])').length"
                ) or 0
                if cnt > 0:
                    break

            # ── Scan all fields ────────────────────────────────────────────
            raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
            fields: list[dict] = _json.loads(raw) if isinstance(raw, str) else (raw or [])
            # Include all fields (not just labelled ones) — same as _apply()
            fillable = [f for f in fields if not str(f.get("selector","")).startswith("__idx__")]
            result["fields_found"] = len(fillable)

            # Save field map
            (job_dir / "form_fields.json").write_text(
                _json.dumps(fields, indent=2, default=str), encoding="utf-8"
            )
            print(f"  📋 {len(fillable)} fillable fields found ({len(fields)} total in scan)")

            if fillable:
                from app.services.job_hunter.apply_service import ApplyService, _make_fill_js

                # Detect combobox fields: when the NEXT raw field has selector '__idx__N'
                # this field is a custom React/Select2 dropdown
                combobox_selectors: set[str] = set()
                for i, f in enumerate(fields):
                    nxt = fields[i + 1] if i + 1 < len(fields) else None
                    if nxt and str(nxt.get("selector","")).startswith("__idx__") and nxt.get("required"):
                        sel = f.get("selector", "")
                        if sel and not sel.startswith("__idx__"):
                            combobox_selectors.add(sel)

                # Pre-read real options from every combobox BEFORE calling Gemini
                # so the LLM gets actual choices instead of guessing blind.
                _fill_svc = ApplyService.__new__(ApplyService)
                if combobox_selectors:
                    print(f"  🔍 Pre-reading options from {len(combobox_selectors)} dropdown(s)…")
                    for field in fillable:
                        sel = field.get("selector", "")
                        if sel in combobox_selectors and not field.get("options"):
                            opts = await _fill_svc._read_combobox_options(browser, page, sel)
                            if opts:
                                field["options"] = opts
                                lbl = (field.get("label") or sel)[:35]
                                print(f"    [{lbl}] → {opts[:5]}")

                # Now call Gemini with full field+options context
                answers = await ApplyService._ai_map_fields_static(fillable, ctx)
                filled  = 0

                for field in fillable:
                    idx      = str(field.get("idx", ""))
                    value    = answers.get(idx, "")
                    selector = field.get("selector", "")
                    ftype    = field.get("type", "text")
                    label    = (field.get("label") or "").strip()

                    if not value:
                        continue
                    if selector.startswith("__idx__"):
                        continue

                    try:
                        if ftype == "file":
                            if ctx.get("resume_pdf") and Path(ctx["resume_pdf"]).exists():
                                await browser.upload_file(page, selector, ctx["resume_pdf"])
                                print(f"    📎 Uploaded resume to [{label}]")
                                resume_uploaded = True
                                filled += 1
                        elif selector in combobox_selectors:
                            # Custom dropdown — click to open, pick best match
                            ok = await _fill_svc._interact_combobox(
                                browser, page, selector, str(value), label
                            )
                            if ok:
                                print(f"    ✔  [dropdown] {label} = {str(value)[:40]}")
                                filled += 1
                            else:
                                print(f"    ⚠️  [dropdown] {label} — no match for '{value[:30]}'")
                        elif len(str(value)) > 80:
                            await browser.fill_field(page, selector, str(value))
                            print(f"    ✔  [textarea] {label} = {str(value)[:40]}…")
                            filled += 1
                        else:
                            await page.evaluate(_make_fill_js(selector, str(value), ftype))
                            print(f"    ✔  [{ftype}] {label} = {str(value)[:40]}")
                            filled += 1
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f"    ⚠️  [{label}] fill failed: {e}")

                result["fields_filled"] = filled
                print(f"  ✅ Filled {filled}/{len(fillable)} fields")

            # ── Resume upload (if file input not caught by scan) ───────────
            if not resume_uploaded and ctx.get("resume_pdf") and Path(ctx["resume_pdf"]).exists():
                try:
                    await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                    print("  📎 Resume upload via direct file input")
                except Exception:
                    pass

            # ── Pause for visual inspection ────────────────────────────────
            if FILLED_PAUSE_SECS > 0:
                print(f"  ⏸  Pausing {FILLED_PAUSE_SECS}s for visual inspection…")
                await asyncio.sleep(FILLED_PAUSE_SECS)

            # ── Screenshot BEFORE submit ───────────────────────────────────
            screenshot_path = job_dir / "screenshot_filled.png"
            try:
                await page.save_screenshot(str(screenshot_path))
                result["screenshot"] = str(screenshot_path)
                print(f"  📸 Screenshot saved: {screenshot_path.name}")
            except Exception as e:
                print(f"  ⚠️  Screenshot failed: {e}")

            if not SUBMIT:
                result["stopped_before_submit"] = True
                print(f"  🛑 Stopped before submit — form NOT submitted (set SUBMIT=1 to submit)")
            else:
                # ── Click submit ───────────────────────────────────────────
                print("  🚀 SUBMIT=1 — clicking submit button…")
                clicked = await browser.click_human(
                    page,
                    '#submit_app, button[type="submit"], input[type="submit"], '
                    '[data-testid*="submit"], [data-testid*="Submit"], '
                    'button[class*="submit"], button[class*="Submit"], '
                    'form button:last-of-type'
                )
                result["submitted"] = clicked
                if not clicked:
                    print("  ⚠️  Submit button not found or not clickable")
                    result["submit_success"] = False
                    result["error"] = "submit button not found"
                else:
                    print("  ⏳ Waiting for confirmation page…")
                    await asyncio.sleep(5)
                    url_after = await browser.current_url(page)
                    from app.services.job_hunter.apply_service import ApplyService
                    success = await ApplyService._is_success_page_static(browser, page, url_after)
                    result["submit_success"] = success
                    result["stopped_before_submit"] = False
                    if success:
                        print(f"  ✅ Submission confirmed — landed on: {url_after[:80]}")
                    else:
                        print(f"  ⚠️  No confirmation detected — final URL: {url_after[:80]}")
                    # Screenshot after submit
                    after_path = job_dir / "screenshot_after_submit.png"
                    try:
                        await page.save_screenshot(str(after_path))
                        result["screenshot_after"] = str(after_path)
                        print(f"  📸 Post-submit screenshot: {after_path.name}")
                    except Exception:
                        pass

    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ❌ Error: {exc}")

    (job_dir / "result.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

async def main(boards: list[str]) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir   = OUTPUT_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  Board Apply Test — {timestamp}")
    print(f"  Boards: {', '.join(boards)}")
    print(f"  Headless: {HEADLESS}  |  Submit: {SUBMIT}  |  Profile: {USE_PROFILE}")
    print(f"  Output: {run_dir}")
    print(f"{'='*70}\n")

    # Generate resume PDF once
    print("📄 Generating test resume PDF…")
    resume_path = _generate_resume_pdf()
    ctx = {**TEST_PROFILE, "resume_pdf": str(resume_path)}

    all_results: list[dict] = []

    for board_id in boards:
        print(f"\n{'─'*60}")
        print(f"🔍 [{board_id.upper()}] Scraping for test job…")

        jobs = await _get_jobs_for_board(board_id)
        if not jobs:
            print(f"  ⚠️  No jobs returned from {board_id} — skipping")
            all_results.append({
                "board": board_id, "error": "no jobs scraped",
                "stopped_before_submit": False,
            })
            continue

        job = jobs[0]
        print(f"  📌 Testing: {job.get('title')} @ {job.get('company')}")
        print(f"  🔗 Apply URL: {(job.get('apply_url') or job.get('url', ''))[:80]}")

        # Put real job title/company into ctx for field-mapping context
        job_ctx = {
            **ctx,
            "job_title": job.get("title", "Software Engineer"),
            "company":   job.get("company", ""),
        }

        result = await _test_apply_board(board_id, job, job_ctx, run_dir)
        all_results.append(result)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Board':<18} {'Job':<30} {'Fields':<12} {'Status'}")
    print(f"  {'─'*18} {'─'*30} {'─'*12} {'─'*20}")

    passed = failed = skipped = 0
    for r in all_results:
        board   = r.get("board", "?")
        company = r.get("company", "")[:14]
        title   = r.get("title",   "")[:14]
        job_str = f"{company}/{title}" if company else "—"
        fields  = f"{r.get('fields_filled',0)}/{r.get('fields_found',0)}"
        error   = r.get("error")

        if r.get("submit_success") is True:
            status = "✅ submitted + confirmed"
            passed += 1
        elif r.get("submitted") and r.get("submit_success") is False:
            status = "⚠️  submitted (no confirm)"
            passed += 1
        elif r.get("stopped_before_submit") and not error:
            status = "✅ filled (no submit)"
            passed += 1
        elif error and "does not support" in (error or ""):
            status = "⏭  skipped (by design)"
            skipped += 1
        elif error and "no jobs" in (error or ""):
            status = "⚠️  no jobs found"
            skipped += 1
        elif error:
            status = f"❌ {error[:35]}"
            failed += 1
        else:
            status = "✅ ok"
            passed += 1

        print(f"  {board:<18} {job_str:<30} {fields:<12} {status}")

    print(f"\n  Passed: {passed}  |  Skipped: {skipped}  |  Failed: {failed}")
    print(f"  Screenshots + field maps: {run_dir}\n")

    # Write summary.md
    md_lines = [
        f"# Apply Test — {timestamp}\n",
        f"Boards tested: {', '.join(boards)}  \n",
        f"Profile: {TEST_PROFILE['full_name']} ({TEST_PROFILE['email']})  \n\n",
        "| Board | Company | Title | Fields Found | Fields Filled | Result |\n",
        "|---|---|---|---|---|---|\n",
    ]
    for r in all_results:
        error = r.get("error", "")
        if r.get("submit_success") is True:
            status = "submitted+confirmed"
        elif r.get("submitted"):
            status = "submitted (no confirm)"
        elif r.get("stopped_before_submit") and not error:
            status = "filled (no submit)"
        else:
            status = f"ERROR: {error}"
        md_lines.append(
            f"| {r.get('board','')} | {r.get('company','')} | {r.get('title','')} "
            f"| {r.get('fields_found',0)} | {r.get('fields_filled',0)} | {status} |\n"
        )
    (run_dir / "summary.md").write_text("".join(md_lines), encoding="utf-8")
    print(f"  Summary written: {run_dir / 'summary.md'}")


if __name__ == "__main__":
    boards_to_test = sys.argv[1:] or ALL_BOARDS
    invalid = [b for b in boards_to_test if b not in ALL_BOARDS]
    if invalid:
        print(f"Unknown boards: {invalid}")
        print(f"Valid options: {ALL_BOARDS}")
        sys.exit(1)
    asyncio.run(main(boards_to_test))
