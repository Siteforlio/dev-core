# backend/app/services/job_hunter/scraper_service.py
import hashlib, uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobListing, JobHunterCampaign
from app.core.config import settings

class ScraperService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def build_url_hash(self, user_id: str, company: str, title: str, apply_url: str) -> str:
        raw = f"{user_id}|{company.lower().strip()}|{title.lower().strip()}|{apply_url.strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def passes_remote_filter(self, job: dict, user_country: str) -> bool:
        if job.get("remote"):
            return True
        loc_country = (job.get("location_country") or "").upper()
        if not loc_country:
            return False  # ambiguous → skip
        return loc_country == user_country.upper()

    async def _call_haiku(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            timeout=10.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    async def score_job_match(self, title: str, description: str, sub_categories: list[str]) -> str:
        prompt = (
            f"Job title: {title}\nDescription (first 500 chars): {description[:500]}\n"
            f"Candidate sub-categories: {', '.join(sub_categories)}\n"
            f"Does this job's CORE requirement match the candidate's specialties? "
            f"Reply with exactly one word: MATCH, PARTIAL, or SKIP."
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
            description=job.get("description", "")[:5000],
            match_score=score,
            sub_category=job.get("sub_category"),
            url_hash=url_hash,
            status="pending" if score != "SKIP" else "skipped",
        )
        self.db.add(listing)
        try:
            await self.db.commit()
            return listing
        except IntegrityError:
            await self.db.rollback()
            return None  # duplicate — silently dropped

    async def run_jobspy(self, campaign: JobHunterCampaign) -> list[dict]:
        """Scrape jobs from multiple sources via JobSpy."""
        import asyncio
        from jobspy import scrape_jobs
        results = await asyncio.to_thread(
            scrape_jobs,
            site_name=["google", "indeed", "glassdoor", "zip_recruiter"],
            search_term=campaign.broad_category,
            results_wanted=50,
            hours_old=24,
        )
        jobs = []
        for _, row in results.iterrows():
            is_remote = str(row.get("is_remote", "")).lower() == "true"
            # skip LinkedIn Easy Apply
            apply_url = str(row.get("job_url_direct") or row.get("job_url") or "")
            if "linkedin.com/jobs/apply" in apply_url:
                continue
            jobs.append({
                "source": "jobspy",
                "title": str(row.get("title") or ""),
                "company": str(row.get("company") or ""),
                "location": str(row.get("location") or "") or None,
                "location_country": (str(row.get("country") or "")[:2].upper()) or None,
                "remote": is_remote,
                "url": str(row.get("job_url") or ""),
                "apply_url": apply_url,
                "description": str(row.get("description") or ""),
            })
        return jobs

    async def scrape_campaign(self, campaign_id: str, user_id: str) -> int:
        result = await self.db.execute(select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id))
        campaign = result.scalar_one()
        raw_jobs = await self.run_jobspy(campaign)
        saved = 0
        for job in raw_jobs:
            if not self.passes_remote_filter(job, campaign.user_country or ""):
                continue
            score = await self.score_job_match(job["title"], job["description"], campaign.sub_categories)
            listing = await self.save_listing(campaign_id, user_id, job, score)
            if listing:
                saved += 1
        return saved
