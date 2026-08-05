# backend/app/services/job_hunter/scraper_service.py
import hashlib, html as _html_mod, sys, uuid, re as _re


def _strip_html(text: str) -> str:
    """Unescape HTML entities then strip all tags, collapse whitespace."""
    text = _html_mod.unescape(text)
    text = _re.sub(r'<[^>]+>', ' ', text)
    text = _re.sub(r'[ \t]+', ' ', text)
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.pg.job_hunter import JobListing, JobHunterCampaign
from app.core.config import settings
from app.services.job_hunter.llm import call_llm

_SCORE_ORDER = {"MATCH": 0, "PARTIAL": 1, "SKIP": 2}

# Generic role-level words that appear in every industry — always let through
_GENERIC_ROLE_WORDS = {
    "manager", "director", "head", "lead", "senior", "junior", "analyst",
    "specialist", "coordinator", "officer", "assistant", "associate",
    "consultant", "advisor", "executive", "intern", "trainee", "supervisor",
    "representative", "administrator", "principal", "partner", "fellow",
}

_LARGE_CORP_SIGNALS = {
    "google", "microsoft", "amazon", "meta", "apple", "ibm", "oracle", "sap",
    "accenture", "deloitte", "pwc", "kpmg", "ernst", "capgemini", "infosys",
    "wipro", "tcs", "cognizant",
}

_STARTUP_NATIVE_SOURCES = {
    "hn_hiring", "remotive", "remoteok", "weworkremotely", "zindi",
    "startupdeals_africa", "fuzu", "brightermonday", "myjobmag",
    "kuhustle", "andela", "arc",
}


def _smb_score(job: dict) -> int:
    """Score a job for SMB/startup preference. Higher = more startup-like. Max 3."""
    score = 0
    if job.get("source", "") in _STARTUP_NATIVE_SOURCES:
        score += 2
    company = (job.get("company") or "").strip().lower()
    if company and not any(sig in company for sig in _LARGE_CORP_SIGNALS):
        score += 1
    return score


async def _run_linkedin_subprocess(li_scraper, broad_category, user_country, work_type, publish_fn):
    """
    On Windows, uvicorn runs on SelectorEventLoop (no create_subprocess_exec) and
    nodriver requires ProactorEventLoop (for create_subprocess_exec to launch Chrome)
    but ProactorEventLoop breaks nodriver's I/O watchers.

    Solution: use a synchronous subprocess.Popen in asyncio.to_thread so the LinkedIn
    runner gets its own fresh process with a default ProactorEventLoop — completely
    isolated from uvicorn's loop. Messages are collected and published after the run.
    """
    import asyncio
    import base64
    import json
    import subprocess
    from pathlib import Path

    runner = Path(__file__).parent / "linkedin_runner.py"
    backend_root = str(runner.parent.parent.parent.parent)

    payload = {
        "email": li_scraper.email,
        "password": li_scraper.password,
        "session_cookie": li_scraper.session_cookie,
        "search_term": broad_category,
        "location": user_country or "",
        "remote_only": work_type == "remote",
        "max_jobs": 150,
    }
    arg = base64.b64encode(json.dumps(payload).encode()).decode()

    collected_logs: list[str] = []
    collected_jobs: list[dict] = []

    def _run_sync():
        try:
            proc = subprocess.Popen(
                [sys.executable, str(runner), arg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=backend_root,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            collected_logs.append(f"❌ LinkedIn: failed to start subprocess — {type(e).__name__}: {e}")
            return

        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "log":
                    collected_logs.append(evt["msg"])
                elif evt.get("type") == "jobs":
                    collected_jobs.extend(evt.get("jobs", []))
                elif evt.get("type") == "error":
                    collected_logs.append(f"❌ LinkedIn error: {evt['msg']}")
        except Exception as e:
            collected_logs.append(f"❌ LinkedIn: stdout read error — {type(e).__name__}: {e}")

        try:
            proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            collected_logs.append("❌ LinkedIn: subprocess timed out after 5 minutes")
            return

        if proc.returncode != 0:
            try:
                stderr = proc.stderr.read().strip()
            except Exception:
                stderr = ""
            last = stderr.splitlines()[-1] if stderr else f"exit code {proc.returncode}"
            collected_logs.append(f"❌ LinkedIn process failed: {last}")

    try:
        await asyncio.to_thread(_run_sync)
    except Exception as e:
        collected_logs.append(f"❌ LinkedIn: to_thread error — {type(e).__name__}: {repr(e)}")

    for msg in collected_logs:
        await publish_fn(msg)

    return collected_jobs


class ScraperService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._campaign_id: str | None = None

    async def _publish(self, message: str) -> None:
        if not self._campaign_id:
            return
        # Use a dedicated session so we never interfere with the main scraper session
        # (calling db.add during an active flush causes SAWarning + session corruption)
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.pg.job_hunter import CampaignActivityLog
            async with AsyncSessionLocal() as log_db:
                log_db.add(CampaignActivityLog(campaign_id=self._campaign_id, message=message))
                await log_db.commit()
        except Exception:
            pass
        # Broadcast to live WebSocket subscribers
        try:
            from app.core.event_bus import publish
            publish(f"campaign:{self._campaign_id}:activity", message)
        except Exception:
            pass

    def build_url_hash(self, user_id: str, company: str, title: str, apply_url: str) -> str:
        raw = f"{user_id}|{company.lower().strip()}|{title.lower().strip()}|{apply_url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    _ONSITE_SIGNALS = {"onsite", "on-site", "on site", "in-office", "in office"}
    _HYBRID_SIGNALS = {"hybrid"}
    _REMOTE_SIGNALS = {"remote", "work from home", "wfh", "distributed", "fully remote"}

    def _job_work_type(self, job: dict) -> str:
        """Detect job's work type from flags and text signals."""
        if job.get("remote"):
            return "remote"
        haystack = " ".join([
            (job.get("title") or ""),
            (job.get("location") or ""),
            (job.get("description") or "")[:200],
        ]).lower()
        if any(s in haystack for s in self._REMOTE_SIGNALS):
            return "remote"
        if any(s in haystack for s in self._HYBRID_SIGNALS):
            return "hybrid"
        if any(s in haystack for s in self._ONSITE_SIGNALS):
            return "onsite"
        return "unknown"

    def passes_work_type_filter(self, job: dict, work_type: str | list, user_country: str, anywhere: bool) -> bool:
        if isinstance(work_type, list):
            if "any" in work_type or not work_type:
                return True
            return any(self.passes_work_type_filter(job, wt, user_country, anywhere) for wt in work_type)

        """Filter jobs by campaign work_type preference and location."""
        if anywhere:
            # No location restriction — only filter by work type
            if work_type == "remote":
                jt = self._job_work_type(job)
                return jt == "remote" or jt == "unknown"  # unknown ambiguous = let through
            return True  # hybrid/onsite/any + anywhere = accept all

        user_c = (user_country or "").upper()
        jt = self._job_work_type(job)
        loc_country = (job.get("location_country") or "").upper()
        is_ats = job.get("source") in ("greenhouse", "lever", "ashby")

        if work_type == "remote":
            if jt == "remote":
                return True
            if jt in ("onsite", "hybrid"):
                return False  # explicitly not remote
            # unknown — ATS jobs pass (they rarely flag remote), jobspy ambiguous skip
            return is_ats

        elif work_type == "onsite":
            if jt == "remote":
                return False
            # Must be in user's country
            if is_ats:
                return True  # ATS: no country data, let through
            return bool(loc_country) and loc_country == user_c

        elif work_type == "hybrid":
            if jt == "remote":
                return False
            if is_ats:
                return True
            return bool(loc_country) and loc_country == user_c

        else:  # "any"
            if is_ats:
                return True
            if jt == "remote":
                return True
            return bool(loc_country) and loc_country == user_c

    async def _call_haiku(self, prompt: str, max_tokens: int = 20) -> str:
        return (await call_llm(prompt, max_tokens, thinking=False)).strip()

    def _keyword_prefilter(self, title: str, description: str, skills: list[str]) -> bool:
        """Fast O(n) check before burning an AI call.
        Returns True if at least 1 skill keyword appears in title+description."""
        if not skills:
            return True  # no skills = no filter, let AI decide
        haystack = (title + " " + description[:2000]).lower()
        for skill in skills:
            if skill.lower() in haystack:
                return True
        return False

    def _category_prefilter(
        self, title: str, description: str,
        broad_category: str, sub_categories: list[str] | None = None,
    ) -> bool:
        """
        Return True if this job is plausibly in the campaign's target categories.
        Uses keywords derived from the campaign's own category names — no hardcoded domain bias.
        Defaults to True (pass through) when uncertain so the AI scorer makes the final call.
        """
        if not broad_category:
            return True  # no category configured — let everything through

        t = title.lower()

        # Generic role-level words present in every field → always pass through
        if any(g in t for g in _GENERIC_ROLE_WORDS):
            return True

        # Build keyword set from campaign category names
        all_cats = [broad_category] + list(sub_categories or [])
        keywords: set[str] = set()
        for cat in all_cats:
            for part in _re.split(r'[\s/\-,]+', cat.lower()):
                if len(part) >= 4:
                    keywords.add(part)
                    # Add stem variants (drop common suffixes)
                    for suffix in ('ing', 'ment', 'tion', 'ers', 'ors', 'ies'):
                        if part.endswith(suffix) and len(part) - len(suffix) >= 4:
                            keywords.add(part[:-len(suffix)])

        # Check title (strongest signal) then description snippet
        d = _re.sub(r'<[^>]+>', ' ', description).lower()[:400]
        if any(kw in t for kw in keywords):
            return True
        if any(kw in d for kw in keywords):
            return True

        # No keyword match — default pass through so AI scorer can decide
        return True

    async def score_job_match(
        self,
        title: str,
        description: str,
        sub_categories: list[str],
        profile_skills: list[str] | None = None,
    ) -> str:
        skills = profile_skills or []

        # Fast pre-filter: if none of the candidate's skills appear at all, skip immediately
        if skills and not self._keyword_prefilter(title, description, skills):
            return "SKIP"

        # Build skill overlap context for AI
        skill_sample = ", ".join(skills[:30]) if skills else "not specified"
        jd_preview = description[:1500]

        prompt = (
            f"You are screening a job listing for a candidate. Reply with exactly one word: MATCH, PARTIAL, or SKIP.\n\n"
            f"Job title: {title}\n"
            f"Job description:\n{jd_preview}\n\n"
            f"Candidate's target roles: {', '.join(sub_categories)}\n"
            f"Candidate's skills/background: {skill_sample}\n\n"
            f"Rules:\n"
            f"- MATCH: The job's core requirements directly align with the candidate's background and target roles\n"
            f"- PARTIAL: Some overlap but the job requires a significantly different primary focus\n"
            f"- SKIP: No meaningful match — clearly the wrong field or requires a background the candidate doesn't have\n"
            f"Reply with exactly one word."
        )
        result = await self._call_haiku(prompt)
        for word in ["MATCH", "PARTIAL", "SKIP"]:
            if word in result.upper():
                return word
        return "SKIP"

    async def save_listing(self, campaign_id: str, user_id: str, job: dict, score: str) -> JobListing | None:
        url_hash = self.build_url_hash(user_id, job.get("company", ""), job.get("title", ""), job.get("apply_url") or job.get("url", ""))
        listing = JobListing(
            id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            source=job.get("source", "unknown"),
            title=job.get("title", ""),
            company=job.get("company", ""),
            location=job.get("location"),
            location_country=job.get("location_country"),
            remote=job.get("remote", False),
            url=job.get("url", ""),
            apply_url=job.get("apply_url"),
            description=_strip_html(job.get("description", ""))[:10000],
            match_score=score,
            sub_category=job.get("sub_category"),
            url_hash=url_hash,
            status="pending" if score != "SKIP" else "skipped",
            posted_at=job.get("posted_at"),
        )
        self.db.add(listing)
        try:
            await self.db.commit()
            return listing
        except IntegrityError:
            await self.db.rollback()
            # Duplicate url_hash — job already exists (possibly from a different campaign).
            # For MATCH or PARTIAL: always reassign to the current campaign if the new score
            # is equal or better, so the job shows up in the correct pipeline.
            if _SCORE_ORDER.get(score, 99) < 2:  # MATCH=0 or PARTIAL=1
                existing = (await self.db.execute(
                    select(JobListing).where(JobListing.url_hash == url_hash)
                )).scalar_one_or_none()
                if existing and _SCORE_ORDER.get(score, 99) <= _SCORE_ORDER.get(existing.match_score, 99):
                    existing.match_score = score
                    existing.status = "pending"
                    existing.campaign_id = campaign_id
                    await self.db.commit()
                    return existing
            return None

    async def run_jobspy(self, campaign: JobHunterCampaign, results_wanted: int = 100, search_term: str | None = None) -> list[dict]:
        """Scrape jobs from multiple sources via JobSpy, tolerating per-source failures."""
        import asyncio
        from jobspy import scrape_jobs

        term = search_term or campaign.broad_category
        sources = ["indeed", "google", "zip_recruiter", "glassdoor"]
        all_rows = []

        for source in sources:
            try:
                results = await asyncio.to_thread(
                    scrape_jobs,
                    site_name=[source],
                    search_term=term,
                    results_wanted=results_wanted,
                    hours_old=48,
                )
                all_rows.append(results)
                await self._publish(f"  ↳ {source}: {len(results)} listings")
            except Exception as e:
                await self._publish(f"  ↳ {source}: skipped ({e})")

        non_empty = [df for df in all_rows if not df.empty]
        if not non_empty:
            return []

        import pandas as pd
        combined = pd.concat(non_empty, ignore_index=True)

        jobs = []
        seen_hashes: set[str] = set()
        for _, row in combined.iterrows():
            is_remote = str(row.get("is_remote", "")).lower() == "true"
            apply_url = str(row.get("job_url_direct") or row.get("job_url") or "")
            if "linkedin.com/jobs/apply" in apply_url:
                continue
            dedup_key = f"{str(row.get('company') or '').lower()}|{str(row.get('title') or '').lower()}"
            if dedup_key in seen_hashes:
                continue
            seen_hashes.add(dedup_key)
            # Parse date_posted — JobSpy returns a date or datetime object
            raw_date = row.get("date_posted")
            posted_at = None
            if raw_date is not None:
                try:
                    from datetime import date as _date, datetime as _datetime, timezone as _tz
                    if isinstance(raw_date, _datetime):
                        posted_at = raw_date.replace(tzinfo=_tz.utc) if raw_date.tzinfo is None else raw_date
                    elif isinstance(raw_date, _date):
                        posted_at = _datetime(raw_date.year, raw_date.month, raw_date.day, tzinfo=_tz.utc)
                except Exception:
                    posted_at = None

            jobs.append({
                "source": str(row.get("site") or "jobspy"),
                "title": str(row.get("title") or ""),
                "company": str(row.get("company") or ""),
                "location": str(row.get("location") or "") or None,
                "location_country": (str(row.get("country") or "")[:2].upper()) or None,
                "remote": is_remote,
                "url": str(row.get("job_url") or ""),
                "apply_url": apply_url,
                "description": str(row.get("description") or ""),
                "posted_at": posted_at,
            })
        return jobs

    async def scrape_campaign(self, campaign_id: str, user_id: str, target: int = 100) -> int:
        import asyncio
        from datetime import datetime, timezone
        from app.services.job_hunter.ats_scrapers import scrape_all_ats
        from app.services.job_hunter.startup_scrapers import scrape_all_startup_boards
        from app.services.job_hunter.kenya_scrapers import scrape_all_kenya_boards

        self._campaign_id = campaign_id
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one()

        # Eagerly read all attributes before any thread boundary
        broad_category = campaign.broad_category
        user_country = campaign.user_country or ""
        sub_categories = list(campaign.sub_categories or [])
        work_type = campaign.work_type or "remote"
        anywhere = bool(campaign.anywhere)
        # Resolve LinkedIn credentials: UserIntegration (global) takes priority over legacy campaign field
        linkedin_creds: dict | None = None
        linkedin_enabled = bool(campaign.linkedin_enabled)
        if linkedin_enabled:
            try:
                from app.services.job_hunter.email_service import EmailService
                from app.models.pg.job_hunter import UserIntegration
                svc = EmailService(self.db)
                ui_result = await self.db.execute(
                    select(UserIntegration).where(UserIntegration.user_id == user_id)
                )
                ui = ui_result.scalar_one_or_none()
                encrypted = (ui.linkedin_account_encrypted if ui else None) or campaign.linkedin_account_encrypted
                if encrypted:
                    linkedin_creds = svc.decrypt_credentials(encrypted)
            except Exception:
                await self._publish("⚠️ LinkedIn: failed to decrypt credentials — skipping LinkedIn source")

        # Load campaign profile for skills-based scoring
        from app.models.pg.job_hunter import CampaignProfile
        profile_result = await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == campaign_id)
        )
        cp = profile_result.scalar_one_or_none()
        profile_skills: list[str] = list(cp.skills or []) if cp else []
        if profile_skills:
            await self._publish(f"🧠 Scoring with {len(profile_skills)} profile skills for better match accuracy")

        deadline = datetime.now(timezone.utc).timestamp() + 86400  # 24h window

        location_label = "anywhere" if anywhere else (user_country or "any country")
        await self._publish(f"🔍 Starting scrape for '{broad_category}' | {work_type} | {location_label} (target: {target} matches, window: 24h)")
        await self._publish(f"📋 Sub-categories: {', '.join(sub_categories)}")

        matches_found = 0  # only MATCH jobs count toward target
        skipped_location = 0
        skipped_non_tech = 0
        skipped_duplicate = 0
        match_counts = {"MATCH": 0, "PARTIAL": 0, "SKIP": 0}
        attempt = 0
        results_wanted = target * 2
        consecutive_empty = 0
        ats_fetched = False    # ATS APIs return static snapshots — only fetch once per campaign run
        kenya_fetched = False  # Kenya boards are fetched on first pass only (alongside ATS)

        while matches_found < target:
            # Check 24h deadline
            remaining_seconds = deadline - datetime.now(timezone.utc).timestamp()
            if remaining_seconds <= 0:
                await self._publish(f"⏰ 24h window reached — stopping at {matches_found}/{target} matches")
                break

            attempt += 1
            remaining_h = int(remaining_seconds // 3600)
            remaining_m = int((remaining_seconds % 3600) // 60)
            await self._publish(
                f"⏳ Pass {attempt} — fetching {results_wanted} listings "
                f"({matches_found}/{target} matches, {remaining_h}h {remaining_m}m remaining)"
            )

            try:
                if not ats_fetched:
                    # First pass: jobspy + ATS company boards + startup boards + LinkedIn in parallel
                    sources_label = "job boards + ATS company boards + startup boards"
                    if linkedin_creds:
                        sources_label += " + LinkedIn"
                    await self._publish(f"🌐 Querying {sources_label} in parallel...")
                    try:
                        gather_coros = [
                            self.run_jobspy(campaign, results_wanted=results_wanted, search_term=broad_category),
                            scrape_all_ats(broad_category, publish_fn=self._publish),
                            scrape_all_startup_boards(broad_category, publish_fn=self._publish),
                            scrape_all_kenya_boards(broad_category, publish_fn=self._publish),
                        ]
                        if linkedin_creds:
                            from app.services.job_hunter.linkedin_scraper import LinkedInScraper
                            li_scraper = LinkedInScraper(
                                email=linkedin_creds.get("email"),
                                password=linkedin_creds.get("password"),
                                session_cookie=linkedin_creds.get("session_cookie"),
                            )
                            gather_coros.append(
                                _run_linkedin_subprocess(
                                    li_scraper, broad_category, user_country,
                                    work_type, self._publish,
                                )
                            )
                        results = await asyncio.gather(*gather_coros, return_exceptions=True)
                        jobspy_jobs  = results[0] if not isinstance(results[0], Exception) else []
                        ats_jobs     = results[1] if not isinstance(results[1], Exception) else []
                        startup_jobs = results[2] if not isinstance(results[2], Exception) else []
                        kenya_jobs   = results[3] if not isinstance(results[3], Exception) else []
                        li_jobs      = results[4] if len(results) > 4 and not isinstance(results[4], Exception) else []
                        if linkedin_creds and len(results) > 4 and isinstance(results[4], Exception):
                            li_err = results[4]
                            li_err_msg = repr(li_err) if not str(li_err) else str(li_err)
                            await self._publish(f"⚠️ LinkedIn scrape error: {type(li_err).__name__}: {li_err_msg}")
                        kenya_fetched = True
                    except Exception as e:
                        await self._publish(f"⚠️ Parallel fetch error ({e}) — falling back to job boards only")
                        jobspy_jobs = await self.run_jobspy(campaign, results_wanted=results_wanted, search_term=broad_category)
                        ats_jobs = []
                        startup_jobs = []
                        kenya_jobs = []
                        li_jobs = []
                    raw_jobs = jobspy_jobs + ats_jobs + startup_jobs + kenya_jobs + li_jobs
                    ats_fetched = True
                else:
                    # Subsequent passes: jobspy + startup boards + LinkedIn (ATS snapshot doesn't change)
                    gather_coros = [
                        self.run_jobspy(campaign, results_wanted=results_wanted, search_term=broad_category),
                        scrape_all_startup_boards(broad_category, publish_fn=self._publish),
                    ]
                    if linkedin_creds:
                        from app.services.job_hunter.linkedin_scraper import LinkedInScraper
                        li_scraper = LinkedInScraper(
                            email=linkedin_creds.get("email"),
                            password=linkedin_creds.get("password"),
                            session_cookie=linkedin_creds.get("session_cookie"),
                        )
                        gather_coros.append(
                            _run_linkedin_subprocess(
                                li_scraper, broad_category, user_country,
                                work_type, self._publish,
                            )
                        )
                    results = await asyncio.gather(*gather_coros, return_exceptions=True)
                    jobspy_jobs  = results[0] if not isinstance(results[0], Exception) else []
                    startup_jobs = results[1] if not isinstance(results[1], Exception) else []
                    li_jobs      = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
                    raw_jobs = jobspy_jobs + startup_jobs + li_jobs
            except Exception as e:
                await self._publish(f"❌ Pass {attempt} failed: {e} — retrying in 5m")
                await asyncio.sleep(300)
                continue

            await self._publish(f"📦 Pass {attempt}: {len(raw_jobs)} raw listings — filtering and scoring...")

            new_matches_this_pass = 0

            # Step 1: work-type filter
            work_type_filtered = []
            for job in raw_jobs:
                if self.passes_work_type_filter(job, work_type, user_country, anywhere):
                    work_type_filtered.append(job)
                else:
                    skipped_location += 1

            # Step 2: category pre-filter (drops jobs clearly outside the campaign's field)
            tech_filtered = []
            for job in work_type_filtered:
                if self._category_prefilter(job["title"], job["description"], broad_category, sub_categories):
                    tech_filtered.append(job)
                else:
                    skipped_non_tech += 1

            # Step 3: sort by SMB score descending so startup-native sources are scored first
            tech_filtered.sort(key=_smb_score, reverse=True)

            # Step 4: score and dispatch
            for job in tech_filtered:
                if matches_found >= target:
                    break

                score = await self.score_job_match(job["title"], job["description"], sub_categories, profile_skills)
                match_counts[score] = match_counts.get(score, 0) + 1

                if score != "SKIP":
                    await self._publish(f"{'✅' if score == 'MATCH' else '🟡'} {score} — {job['title']} @ {job['company']}")

                listing = await self.save_listing(campaign_id, user_id, job, score)
                if listing:
                    if score == "MATCH":
                        matches_found += 1
                        new_matches_this_pass += 1
                        # Dispatch tailor → apply pipeline via asyncio task runner
                        try:
                            from app.core.task_runner import get_runner
                            from app.workers.tailor_worker import tailor_listing
                            get_runner().submit(tailor_listing(listing.id, user_id))
                        except Exception as e:
                            await self._publish(f"⚠️ Failed to queue tailor task for {listing.id}: {e}")
                elif score == "MATCH":
                    skipped_duplicate += 1

            await self._publish(f"📊 Pass {attempt} complete — {new_matches_this_pass} new matches ({matches_found}/{target} matches total)")

            if new_matches_this_pass == 0:
                consecutive_empty += 1
                wait_minutes = min(15 * consecutive_empty, 60)  # backoff: 15m, 30m, 60m cap
                await self._publish(f"⏸ No new matches — waiting {wait_minutes}m before retrying (sources need to refresh)")
                await asyncio.sleep(wait_minutes * 60)
            else:
                consecutive_empty = 0
                results_wanted = max(results_wanted, (target - matches_found) * 2)

        await self._publish(
            f"✔ Done — {matches_found} matches found | "
            f"{match_counts['PARTIAL']} partial, {match_counts['SKIP']} skipped | "
            f"{skipped_location} filtered by location | {skipped_non_tech} non-tech filtered | "
            f"{skipped_duplicate} duplicates"
        )
        return matches_found
