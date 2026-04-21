#!/usr/bin/env python
# backend/tests/integration/test_tailor_audit.py
"""
Tailor Audit — scrape real job boards, inspect every apply form, build tailored
resumes, and dump everything to a local folder WITHOUT submitting anything.

Output layout:
  tailor_audit_output/
    YYYY-MM-DD_HH-MM-SS/
      summary.md                  ← human-readable table of all jobs + fit scores
      job_001_<title>_<company>/
        job_details.json          ← title, company, description, apply_url, source, fit_score
        form_fields.json          ← every field/question found on the apply form
        resume.html               ← tailored resume (open in browser)
        cover_letter.txt          ← tailored cover letter
      job_002_...

Usage:
    cd backend
    python tests/integration/test_tailor_audit.py

Optional flags (edit CONFIG section below):
    BOARDS_TO_USE   — which boards to hit
    JOBS_PER_BOARD  — how many jobs to collect per board
    MAX_APPLY_JOBS  — how many apply-form inspections to run (browser opens for each)
    MIN_FIT_SCORE   — skip form inspection + tailoring below this threshold
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import httpx

# Windows: ProactorEventLoop required for nodriver (Chrome subprocess)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — edit these to suit your run
# ─────────────────────────────────────────────────────────────────────────────

BOARDS_TO_USE = [
    "remotive",
    "remoteok",
    "weworkremotely",
    "brightermonday",
    "myjobmag",
]

JOBS_PER_BOARD  = 5    # jobs collected per board
MAX_APPLY_JOBS  = 10   # max browser inspections (browser opens for each — slow)
MIN_FIT_SCORE   = 0.20 # skip tailoring below this score (0 = tailor everything)

# ── Test profile — edit this to match your real background ───────────────────
TEST_PROFILE = {
    "full_name":          "Alex Mwangi",
    "email":              "alex.mwangi@example.com",
    "phone":              "+254 700 000000",
    "city":               "Nairobi",
    "country":            "Kenya",
    "linkedin_url":       "https://linkedin.com/in/alexmwangi",
    "github_url":         "https://github.com/alexmwangi",
    "portfolio_url":      "https://alexmwangi.dev",
    "years_of_experience": 5,
    "skills": [
        "Python", "FastAPI", "Django", "React", "TypeScript", "PostgreSQL",
        "Redis", "Docker", "AWS", "Celery", "SQLAlchemy", "REST APIs",
        "CI/CD", "GitHub Actions", "Linux", "Git",
    ],
    "work_experience": [
        {
            "title":    "Senior Backend Engineer",
            "company":  "Fintech Startup",
            "location": "Nairobi, Kenya",
            "start_date": "Jan 2022",
            "end_date":   "Present",
            "responsibilities": [
                "Built payment processing APIs handling 50,000 transactions per day with 99.9% uptime",
                "Reduced API response time by 40% by introducing Redis caching layer",
                "Led migration from monolith to microservices, cutting deployment time from 2 hours to 8 minutes",
                "Mentored 3 junior engineers and ran weekly code reviews",
            ],
        },
        {
            "title":    "Backend Developer",
            "company":  "E-commerce Platform",
            "location": "Remote",
            "start_date": "Mar 2020",
            "end_date":   "Dec 2021",
            "responsibilities": [
                "Developed order management system serving 200,000 active users",
                "Integrated 5 payment gateways (M-Pesa, Stripe, PayPal, Flutterwave, Pesalink)",
                "Automated reporting pipeline saving 20 hours of manual work per week",
            ],
        },
    ],
    "education": [
        {
            "degree": "BSc Computer Science",
            "field_of_study": "Computer Science",
            "institution": "University of Nairobi",
            "graduation_year": 2019,
        }
    ],
    "projects": [
        {
            "name": "DevCore Job Hunter",
            "description": "AI-powered job scraper and auto-apply system",
            "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Celery"],
            "link": "https://github.com/alexmwangi/devcore",
        }
    ],
    "achievements": [
        "Reduced cloud infrastructure cost by 35% through right-sizing and Reserved Instances",
        "Open-source contributor: 200+ GitHub stars on redis-cache-utils library",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_BASE = Path(__file__).parent.parent.parent.parent / "tailor_audit_output"

SEP = "─" * 80


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:30]


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Scrape job boards
# ─────────────────────────────────────────────────────────────────────────────

async def _scrape_boards(client: httpx.AsyncClient) -> list[dict]:
    from app.services.job_hunter.startup_scrapers import (
        scrape_remotive, scrape_remoteok, scrape_weworkremotely,
    )
    from app.services.job_hunter.kenya_scrapers import (
        scrape_brightermonday, scrape_myjobmag, scrape_fuzu,
        scrape_kuhustle, scrape_andela, scrape_arc,
    )
    from app.services.job_hunter.scraper_service import (
        _TECH_REJECT_SIGNALS, _TECH_ACCEPT_SIGNALS,
    )

    BOARD_MAP = {
        "remotive":       (scrape_remotive,       False),
        "remoteok":       (scrape_remoteok,        False),
        "weworkremotely": (scrape_weworkremotely,  False),
        "brightermonday": (scrape_brightermonday,  True),
        "myjobmag":       (scrape_myjobmag,        False),
        "fuzu":           (scrape_fuzu,            True),
        "kuhustle":       (scrape_kuhustle,        False),
        "andela":         (scrape_andela,          True),
        "arc":            (scrape_arc,             True),
    }

    TERMS = ["software engineer", "backend developer", "python developer", "data engineer"]

    def _is_tech(title: str, desc: str) -> bool:
        t = title.lower()
        if any(s in t for s in _TECH_REJECT_SIGNALS):
            return False
        if any(s in t for s in _TECH_ACCEPT_SIGNALS):
            return True
        return any(s in _strip_html(desc).lower()[:300] for s in _TECH_ACCEPT_SIGNALS)

    async def scrape_one(name: str) -> list[dict]:
        fn, uses_browser = BOARD_MAP.get(name, (None, False))
        if fn is None:
            _log(f"  SKIP {name} — not in board map")
            return []
        collected: list[dict] = []
        _log(f"  scraping {name} ...")
        for term in TERMS:
            if len(collected) >= JOBS_PER_BOARD:
                break
            try:
                kwargs = {"search_term": term}
                if uses_browser:
                    kwargs["headless"] = True
                raw = await fn(client=client, **kwargs)
                for job in raw:
                    if len(collected) >= JOBS_PER_BOARD:
                        break
                    title = (job.get("title") or "")
                    desc  = (job.get("description") or "")
                    if _is_tech(title, desc):
                        job["source"] = name
                        collected.append(job)
            except Exception as exc:
                _log(f"    {name}/{term} error: {exc}")
        _log(f"  {name}: {len(collected)} jobs")
        return collected

    boards_to_run = [b for b in BOARDS_TO_USE if b in BOARD_MAP]
    results = await asyncio.gather(*[scrape_one(b) for b in boards_to_run])
    all_jobs = [j for batch in results for j in batch]
    _log(f"Total scraped: {len(all_jobs)} tech jobs across {len(boards_to_run)} boards")
    return all_jobs


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Score fit for every job (local BERT, no API calls)
# ─────────────────────────────────────────────────────────────────────────────

def _score_all(jobs: list[dict]) -> list[dict]:
    from app.services.job_hunter.matcher_service import matcher

    profile_text = (
        f"{', '.join(TEST_PROFILE['skills'][:20])} | "
        f"{' | '.join(j['title'] for j in TEST_PROFILE['work_experience'][:2])} | "
        f"{TEST_PROFILE['years_of_experience']} years experience"
    )
    for job in jobs:
        jd = _strip_html(job.get("description") or job.get("title") or "")
        job["fit_score"] = matcher.score_fit(jd, profile_text) if jd else 0.0

    jobs.sort(key=lambda j: j["fit_score"], reverse=True)
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Inspect apply form (browser, no submission)
# ─────────────────────────────────────────────────────────────────────────────

async def _inspect_form(apply_url: str) -> dict:
    """
    Navigate to the apply URL, scan every visible form field, and return a
    structured dict.  Never fills or submits anything.

    Returns:
      {
        "url_visited": str,
        "ats": str,
        "fields": [ {label, type, options, required, selector} ... ],
        "questions": [ str, ... ],   # text/textarea fields that look like questions
        "error": str | None,
      }
    """
    from app.services.job_hunter.apply_service import (
        ApplyService, _SCAN_FIELDS_JS, ATS_PATTERNS,
    )
    from app.services.job_hunter.browser_service import BrowserService

    result: dict = {
        "url_visited": apply_url,
        "ats":         "unknown",
        "fields":      [],
        "questions":   [],
        "error":       None,
    }

    # Detect ATS type
    url_lower = apply_url.lower()
    for ats_name, patterns in ATS_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            result["ats"] = ats_name
            break

    if result["ats"] == "skip":
        result["error"] = "LinkedIn direct-apply — cannot inspect without auth"
        return result

    # Try HTTP pre-detection first (no browser needed)
    svc = ApplyService.__new__(ApplyService)
    try:
        form_url = await svc._detect_form_url(apply_url)
        navigate_to = form_url or apply_url
        result["url_visited"] = navigate_to
    except Exception as exc:
        navigate_to = apply_url
        result["error"] = f"_detect_form_url failed: {exc}"

    # Open browser, navigate, scan fields
    try:
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            await browser.goto(page, navigate_to, wait=5.0)
            await browser.wait_past_cloudflare(page)

            # Poll for fields to appear (React SPAs render asynchronously)
            for _ in range(20):
                await asyncio.sleep(0.5)
                count = await page.evaluate(
                    "document.querySelectorAll("
                    "'input:not([type=hidden]):not([disabled]),"
                    "select:not([disabled]),textarea:not([disabled])').length"
                ) or 0
                if count > 0:
                    break

            raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
            fields = json.loads(raw) if isinstance(raw, str) else (raw or [])

            for f in fields:
                label   = (f.get("label") or "").strip()
                ftype   = f.get("type", "text")
                opts    = f.get("options") or []
                req     = f.get("required", False)
                sel     = f.get("selector", "")

                # Normalise options list
                opt_labels = []
                for o in opts[:10]:
                    opt_labels.append(o["label"] if isinstance(o, dict) else str(o))

                result["fields"].append({
                    "label":    label,
                    "type":     ftype,
                    "options":  opt_labels,
                    "required": req,
                    "selector": sel,
                })

                # Flag text/textarea with question-like labels as "questions"
                if ftype in ("text", "textarea") and label and (
                    "?" in label
                    or any(kw in label.lower() for kw in [
                        "why", "describe", "tell us", "explain", "how", "what",
                        "experience", "cover", "additional", "comment",
                    ])
                ):
                    result["questions"].append(label)

    except Exception as exc:
        result["error"] = f"browser error: {exc}"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Tailor resume (no DB — uses the raw LLM methods directly)
# ─────────────────────────────────────────────────────────────────────────────

async def _tailor_job(job: dict) -> dict:
    """
    Run the full tailoring pipeline against a job dict using TEST_PROFILE.
    Returns {"html": str, "cover_letter": str, "keywords": list, "summary": str}
    """
    from app.services.job_hunter.tailor_service import TailorService
    from app.services.job_hunter.matcher_service import matcher

    # Build a minimal mock profile object from TEST_PROFILE dict
    class _Profile:
        full_name          = TEST_PROFILE["full_name"]
        email              = TEST_PROFILE["email"]
        phone              = TEST_PROFILE["phone"]
        city               = TEST_PROFILE["city"]
        country            = TEST_PROFILE["country"]
        linkedin_url       = TEST_PROFILE["linkedin_url"]
        github_url         = TEST_PROFILE["github_url"]
        portfolio_url      = TEST_PROFILE["portfolio_url"]
        years_of_experience = TEST_PROFILE["years_of_experience"]
        skills             = TEST_PROFILE["skills"]
        work_experience    = TEST_PROFILE["work_experience"]
        education          = TEST_PROFILE["education"]
        projects           = TEST_PROFILE["projects"]
        achievements       = TEST_PROFILE["achievements"]

    profile = _Profile()
    svc = TailorService(db=None)  # db not used in the methods we call

    jd        = _strip_html(job.get("description") or "")
    title     = (job.get("title") or "Unknown Role")[:150]
    company   = (job.get("company") or "Unknown")[:100]
    location  = (job.get("location") or "remote")[:100]

    # --- Keyword extraction (1 LLM call) ---
    keywords = await svc.extract_keywords(jd) if jd else []

    # --- Local skill matching (0 LLM calls) ---
    top_competencies = svc.pick_top_competencies(jd or title, profile.skills)
    resume_skills    = svc.pick_resume_skills(jd or title, profile.skills)

    # --- Parallel LLM calls: summary + salary + bullets ---
    bullet_pairs = svc._extract_bullets(profile.work_experience)
    bullets_only = [b for _, b in bullet_pairs]
    jd_summary   = jd[:400]

    summary, salary, rewritten = await asyncio.gather(
        svc.generate_summary(profile, keywords, title),
        svc.infer_salary(profile.years_of_experience, location, company),
        svc.rewrite_bullets(
            bullets_only[:20], keywords,
            target_role=title, target_company=company, jd_summary=jd_summary,
        ),
    )

    # --- Cover letter (1 LLM call) ---
    cover_letter = await svc._call_haiku(
        f"Write a concise 3-paragraph cover letter for {title} at {company}.\n"
        f"The candidate's name is {profile.full_name}.\n"
        f"Opening: show genuine interest in the company and role.\n"
        f"Middle: highlight 2-3 specific achievements from their experience.\n"
        f"Closing: express enthusiasm and salary expectation of {salary}.\n"
        f"Candidate skills: {', '.join(profile.skills[:10])}.\n"
        f"JD keywords to address: {', '.join(keywords[:8])}.\n"
        f"End with 'Sincerely,' then '{profile.full_name}'. No markdown.",
        max_tokens=500,
    )

    # --- Map rewritten bullets back to jobs ---
    rewritten_by_job: dict[int, list[str]] = {}
    for idx, (job_idx, _) in enumerate(bullet_pairs[:20]):
        rewritten_by_job.setdefault(job_idx, []).append(
            rewritten[idx] if idx < len(rewritten) else bullets_only[idx]
        )

    # --- Build HTML ---
    html = svc._build_html(
        profile=profile,
        experience=profile.work_experience,
        rewritten_by_job=rewritten_by_job,
        keywords=keywords,
        top_competencies=top_competencies,
        summary=summary,
        salary=salary,
        resume_skills=resume_skills,
    )

    return {
        "html":         html,
        "cover_letter": cover_letter,
        "keywords":     keywords,
        "summary":      summary,
        "salary":       salary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Save everything to disk
# ─────────────────────────────────────────────────────────────────────────────

def _save_job(
    out_dir: Path,
    idx: int,
    job: dict,
    form_result: dict | None,
    tailor_result: dict | None,
) -> None:
    slug    = f"job_{idx:03d}_{_slugify(job.get('title',''))[:20]}_{_slugify(job.get('company',''))[:15]}"
    job_dir = out_dir / slug
    job_dir.mkdir(parents=True, exist_ok=True)

    # job_details.json
    details = {
        "title":       job.get("title"),
        "company":     job.get("company"),
        "location":    job.get("location"),
        "remote":      job.get("remote"),
        "source":      job.get("source"),
        "apply_url":   job.get("apply_url") or job.get("url"),
        "fit_score":   round(job.get("fit_score", 0), 4),
        "description": _strip_html(job.get("description") or "")[:5000],
        "tags":        job.get("tags") or job.get("tech_stack") or [],
    }
    (job_dir / "job_details.json").write_text(
        json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # form_fields.json
    if form_result:
        (job_dir / "form_fields.json").write_text(
            json.dumps(form_result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # resume.html
    if tailor_result and tailor_result.get("html"):
        (job_dir / "resume.html").write_text(tailor_result["html"], encoding="utf-8")

    # cover_letter.txt
    if tailor_result and tailor_result.get("cover_letter"):
        (job_dir / "cover_letter.txt").write_text(
            tailor_result["cover_letter"], encoding="utf-8"
        )

    _log(f"  saved → {job_dir.name}/")


def _write_summary(out_dir: Path, jobs: list[dict], form_results: dict, tailor_results: dict) -> None:
    lines = [
        "# Tailor Audit Summary",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Profile: {TEST_PROFILE['full_name']} — {TEST_PROFILE['years_of_experience']} yrs exp",
        "",
        f"{'#':<5} {'Score':<7} {'Title':<40} {'Company':<25} {'Source':<18} {'ATS':<12} {'Fields':<7} {'Questions'}",
        "─" * 140,
    ]
    for i, job in enumerate(jobs, 1):
        fr    = form_results.get(i)
        score = f"{job.get('fit_score', 0):.3f}"
        title = (job.get("title") or "")[:38]
        co    = (job.get("company") or "")[:23]
        src   = (job.get("source") or "")[:16]
        ats   = (fr["ats"] if fr else "—")[:10]
        nf    = len(fr["fields"]) if fr else "—"
        nq    = len(fr["questions"]) if fr else "—"
        lines.append(f"{i:<5} {score:<7} {title:<40} {co:<25} {src:<18} {ats:<12} {str(nf):<7} {nq}")

    lines += ["", "## Questions found on apply forms", ""]
    for i, job in enumerate(jobs, 1):
        fr = form_results.get(i)
        if fr and fr.get("questions"):
            title = (job.get("title") or "")
            lines.append(f"### {i}. {title} @ {job.get('company')}")
            for q in fr["questions"]:
                lines.append(f"  - {q}")
            lines.append("")

    lines += ["", "## Tailoring keywords extracted", ""]
    for i, job in enumerate(jobs, 1):
        tr = tailor_results.get(i)
        if tr and tr.get("keywords"):
            title = (job.get("title") or "")
            lines.append(f"**{i}. {title}**: {', '.join(tr['keywords'][:10])}")

    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    _log(f"Summary written → {out_dir / 'summary.md'}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    run_ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = OUTPUT_BASE / run_ts
    out_dir.mkdir(parents=True, exist_ok=True)
    _log(f"Output folder: {out_dir}")

    # ── 1. Scrape ─────────────────────────────────────────────────────────────
    _log(SEP)
    _log("STEP 1 — Scraping job boards")
    _log(SEP)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        jobs = await _scrape_boards(client)

    if not jobs:
        _log("No jobs scraped — check network / board selectors")
        return

    # ── 2. Score fit ──────────────────────────────────────────────────────────
    _log(SEP)
    _log("STEP 2 — Scoring job fit (local BERT)")
    _log(SEP)
    jobs = _score_all(jobs)
    for i, j in enumerate(jobs[:20], 1):
        _log(f"  {i:>3}. [{j['fit_score']:.3f}] {j.get('title','')[:45]}  @  {j.get('company','')[:25]}  ({j.get('source','')})")

    # ── 3. Pick top jobs for apply inspection ─────────────────────────────────
    candidates = [j for j in jobs if j.get("fit_score", 0) >= MIN_FIT_SCORE]
    to_inspect = candidates[:MAX_APPLY_JOBS]
    _log(f"\n{len(to_inspect)} jobs selected for form inspection (fit >= {MIN_FIT_SCORE})")

    # ── 3. Inspect apply forms ────────────────────────────────────────────────
    _log(SEP)
    _log("STEP 3 — Inspecting apply forms (headless browser, no submit)")
    _log(SEP)
    form_results: dict[int, dict] = {}
    for i, job in enumerate(to_inspect, 1):
        apply_url = job.get("apply_url") or job.get("url") or ""
        _log(f"  [{i}/{len(to_inspect)}] {job.get('title','')[:45]} @ {job.get('company','')[:25]}")
        _log(f"    URL: {apply_url[:90]}")
        if not apply_url:
            _log("    SKIP — no apply URL")
            form_results[i] = {"url_visited": "", "ats": "none", "fields": [], "questions": [], "error": "no apply URL"}
            continue
        try:
            fr = await _inspect_form(apply_url)
            form_results[i] = fr
            _log(f"    ATS: {fr['ats']}  |  Fields: {len(fr['fields'])}  |  Questions: {len(fr['questions'])}")
            if fr.get("error"):
                _log(f"    WARNING: {fr['error']}")
            for q in fr["questions"]:
                _log(f"      ? {q[:80]}")
        except Exception as exc:
            _log(f"    ERROR: {exc}")
            form_results[i] = {"url_visited": apply_url, "ats": "error", "fields": [], "questions": [], "error": str(exc)}

    # ── 4. Tailor resumes ─────────────────────────────────────────────────────
    _log(SEP)
    _log("STEP 4 — Tailoring resumes")
    _log(SEP)
    tailor_results: dict[int, dict] = {}
    for i, job in enumerate(to_inspect, 1):
        _log(f"  [{i}/{len(to_inspect)}] tailoring for {job.get('title','')[:40]} @ {job.get('company','')[:25]} ...")
        try:
            tr = await _tailor_job(job)
            tailor_results[i] = tr
            _log(f"    keywords: {', '.join(tr['keywords'][:8])}")
            _log(f"    salary:   {tr['salary']}")
        except Exception as exc:
            _log(f"    ERROR: {exc}")
            tailor_results[i] = {}

    # ── 5. Save ───────────────────────────────────────────────────────────────
    _log(SEP)
    _log("STEP 5 — Saving output")
    _log(SEP)
    for i, job in enumerate(to_inspect, 1):
        _save_job(
            out_dir, i, job,
            form_result   = form_results.get(i),
            tailor_result = tailor_results.get(i),
        )
    _write_summary(out_dir, to_inspect, form_results, tailor_results)

    _log(SEP)
    _log(f"Done. Open this folder to review:")
    _log(f"  {out_dir}")
    _log(f"  summary.md    — overview table + questions found + keywords")
    _log(f"  job_NNN_*/resume.html       — open in browser to see tailored resume")
    _log(f"  job_NNN_*/form_fields.json  — every field on the apply form")
    _log(f"  job_NNN_*/cover_letter.txt  — tailored cover letter")
    _log(SEP)


if __name__ == "__main__":
    asyncio.run(main())
