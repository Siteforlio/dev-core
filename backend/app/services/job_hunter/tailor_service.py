# backend/app/services/job_hunter/tailor_service.py
import json, uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobListing, JobHunterProfile, Application
from app.core.config import settings

class TailorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_haiku(self, prompt: str, max_tokens: int = 1000) -> str:
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            timeout=30.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else ""

    async def extract_keywords(self, jd: str) -> list[str]:
        raw = await self._call_haiku(
            f"Extract the 15 most important ATS keywords from this job description. Return a JSON array of strings only.\n\n{jd[:3000]}"
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return []

    async def rewrite_bullets(self, bullets: list[str], keywords: list[str]) -> list[str]:
        raw = await self._call_haiku(
            f"Rewrite these resume bullets to naturally include relevant keywords. "
            f"Never invent experience — only reformulate using JD vocabulary. "
            f"Keywords: {', '.join(keywords[:10])}. Bullets: {json.dumps(bullets)}. "
            f"Return a JSON array of rewritten bullet strings."
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return bullets  # fallback: return originals
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return bullets

    async def infer_salary(self, seniority: str, location: str, company: str) -> str:
        return await self._call_haiku(
            f"What is a realistic salary range for a {seniority}-level developer in {location} at a {company}? "
            f"Return only the range as a string, e.g. '$90,000 - $120,000'.",
            max_tokens=50,
        )

    async def generate_summary(self, profile: JobHunterProfile, keywords: list[str], role: str) -> str:
        return await self._call_haiku(
            f"Write a 2-3 sentence professional summary for a {role} role. "
            f"Profile skills: {', '.join((profile.skills or [])[:10])}. "
            f"Inject these keywords naturally: {', '.join(keywords[:8])}. "
            f"Return only the summary text.",
            max_tokens=200,
        )

    async def tailor_for_listing(self, listing_id: str, user_id: str) -> Application | None:
        # Idempotency check — prevent duplicate applications on retry
        existing_result = await self.db.execute(
            select(Application).where(
                Application.job_listing_id == listing_id,
                Application.user_id == user_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return existing

        listing_result = await self.db.execute(select(JobListing).where(JobListing.id == listing_id))
        listing = listing_result.scalar_one_or_none()
        if not listing or not listing.description:
            return None

        profile_result = await self.db.execute(select(JobHunterProfile).where(JobHunterProfile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return None

        # Truncate external strings before interpolating into prompts
        company = (listing.company or "")[:100]
        title = (listing.title or "")[:150]
        location = (listing.location or "remote")[:100]

        keywords = await self.extract_keywords(listing.description)
        experience = profile.work_experience or []
        all_bullets = [
            b for job in experience
            for b in (job.get("responsibilities", "").split("\n") if isinstance(job.get("responsibilities"), str) else [])
        ]
        rewritten = await self.rewrite_bullets(all_bullets[:10], keywords) if all_bullets else []
        seniority = "mid"
        salary = await self.infer_salary(seniority, location, company)
        summary = await self.generate_summary(profile, keywords, title)
        cover_letter = await self._call_haiku(
            f"Write a concise cover letter for {title} at {company}. "
            f"Profile: {', '.join((profile.skills or [])[:8])}. Salary expectation: {salary}. "
            f"Keywords: {', '.join(keywords[:8])}. Return only the letter text.",
            max_tokens=400,
        )

        application = Application(
            id=str(uuid.uuid4()),
            campaign_id=listing.campaign_id,
            job_listing_id=listing.id,
            user_id=user_id,
            cover_letter=cover_letter,
            form_answers={"salary": salary, "summary": summary, "rewritten_bullets": rewritten},
            status="applied",
        )
        listing.status = "applying"
        self.db.add(application)
        await self.db.commit()
        return application
