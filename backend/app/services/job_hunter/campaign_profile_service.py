# backend/app/services/job_hunter/campaign_profile_service.py
import json
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import CampaignProfile, JobHunterCampaign
from app.core.config import settings
from app.services.job_hunter.llm import call_llm

logger = logging.getLogger(__name__)

JOB_CATEGORIES = [
    "Software Engineering",
    "Frontend Development",
    "Backend Development",
    "Full Stack Development",
    "Mobile Development",
    "AI / Machine Learning",
    "Data Science",
    "Data Engineering",
    "DevOps / Infrastructure",
    "Cloud Engineering",
    "Cybersecurity",
    "QA / Testing",
    "Product Management",
    "UI/UX Design",
    "Technical Writing",
    "Engineering Management",
]

WORK_TYPES = ["remote", "hybrid", "onsite", "any"]


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CampaignProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, campaign_id: str, user_id: str) -> CampaignProfile:
        result = await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == campaign_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            profile = CampaignProfile(
                id=str(uuid.uuid4()),
                campaign_id=campaign_id,
                user_id=user_id,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            self.db.add(profile)
            await self.db.commit()
        return profile

    async def upsert(self, campaign_id: str, user_id: str, data: dict) -> CampaignProfile:
        profile = await self.get_or_create(campaign_id, user_id)
        for field in [
            "full_name", "email", "phone", "city", "country",
            "linkedin_url", "github_url", "portfolio_url",
            "work_experience", "education", "skills", "projects",
            "languages_spoken", "achievements", "raw_context",
        ]:
            if field in data:
                setattr(profile, field, data[field])
        profile.updated_at = utcnow()
        await self.db.commit()
        return profile

    async def analyze_gaps(self, campaign_id: str, user_id: str) -> dict:
        """
        AI reads the candidate's raw context directly and acts as an internal reviewer.
        Checks whether the profile has enough information for a strong resume.
        Returns score, gaps, questions, and a summary.
        """
        profile = await self.get_or_create(campaign_id, user_id)

        # Get campaign context
        camp_result = await self.db.execute(
            select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id)
        )
        campaign = camp_result.scalar_one_or_none()
        category = campaign.broad_category if campaign else "Software Engineering"
        sub_cats = list(campaign.sub_categories or []) if campaign else []
        role_context = category + (f" ({', '.join(sub_cats)})" if sub_cats else "")

        raw_context = (profile.raw_context or "").strip()
        if not raw_context:
            return {
                "score": 0, "is_ready": False,
                "gaps": ["No profile context yet — paste your CV or describe your experience to get started."],
                "questions": [], "summary": "No information submitted yet.",
            }

        # Trim to ~8000 chars to stay within token budget while preserving key content
        context_for_llm = raw_context[:8000]

        # Quick facts from regex extraction (free signals for the LLM)
        quick_facts = (
            f"- Email on file: {bool(profile.email)}\n"
            f"- Phone on file: {bool(profile.phone)}\n"
            f"- LinkedIn on file: {bool(profile.linkedin_url)}\n"
            f"- GitHub on file: {bool(profile.github_url)}\n"
            f"- Years of experience stated: {profile.years_of_experience if profile.years_of_experience is not None else 'not found'}\n"
            f"- Skills detected: {len(profile.skills or [])} ({', '.join((profile.skills or [])[:15])})"
        )

        prompt = (
            f"You are reviewing a job candidate's profile for a {role_context} role.\n\n"
            f"Below is the candidate's raw profile context (exactly what they submitted):\n"
            f"---\n{context_for_llm}\n---\n\n"
            f"Quick extracted facts:\n{quick_facts}\n\n"
            f"Read the raw context above and determine whether this candidate has enough information "
            f"to generate a strong, ATS-matched resume for {role_context}.\n\n"
            f"Respond with a JSON object:\n"
            f'{{\n'
            f'  "score": <0-100 integer>,\n'
            f'  "is_ready": <true if score >= 75>,\n'
            f'  "gaps": ["specific gap — e.g. \'No quantified impact in work bullets — add metrics like users served, latency reduced, revenue impacted\'", ...],\n'
            f'  "questions": [{{"gap": "gap label", "question": "specific pre-screen question to fill this gap"}}],\n'
            f'  "summary": "one sentence: main strength + single biggest thing holding this profile back"\n'
            f'}}\n\n'
            f"SCORING (start at 100, deduct):\n"
            f"- -20 if no work experience described (no companies, titles, or job descriptions)\n"
            f"- -15 if years of experience not stated\n"
            f"- -10 if no quantified achievements (no numbers, %, metrics anywhere in work history)\n"
            f"- -10 if fewer than 5 skills relevant to {category} mentioned\n"
            f"- -10 if no contact info found (name/email/phone)\n"
            f"- -5 if no LinkedIn URL\n"
            f"- -5 if no GitHub URL\n"
            f"- -8 if work descriptions are vague (no specific responsibilities or outcomes — just titles)\n"
            f"- +5 if detailed project descriptions with measurable outcomes are present\n"
            f"- +5 if candidate clearly owns end-to-end work (built, designed, led — not just 'helped')\n\n"
            f"GAPS: be specific to {role_context} — name the exact ATS keywords missing, "
            f"the specific metrics absent, the ownership signals weak.\n"
            f"QUESTIONS: ask like a hiring manager pre-screen — name the company, ask for numbers.\n"
            f"NEVER flag high skill counts. NEVER ask for info that's already clearly present.\n"
            f"Return only the JSON object, no other text."
        )

        try:
            raw = await call_llm(prompt, max_tokens=2000, json_mode=True, thinking=False)
        except Exception:
            logger.exception("analyze_gaps: LLM call failed")
            return {"score": 0, "is_ready": False, "gaps": ["Could not analyze profile"], "questions": [], "summary": "Analysis failed"}

        if not raw:
            logger.error("analyze_gaps: LLM returned empty string for campaign=%s", campaign_id)
            return {"score": 0, "is_ready": False, "gaps": ["Could not analyze profile"], "questions": [], "summary": "Analysis failed"}

        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("analyze_gaps: no JSON braces in response: %r", raw[:200])
            return {"score": 0, "is_ready": False, "gaps": ["Could not analyze profile"], "questions": [], "summary": "Analysis failed"}
        try:
            result = json.loads(raw[start:end])
            profile.completion_gaps = result.get("gaps", [])
            profile.is_complete = result.get("is_ready", False)
            await self.db.commit()
            return result
        except json.JSONDecodeError:
            logger.error("analyze_gaps: JSON parse failed: %r", raw[:200])
            return {"score": 0, "is_ready": False, "gaps": ["Could not parse AI response"], "questions": [], "summary": "Analysis failed"}

    async def process_raw_context(self, campaign_id: str, user_id: str, raw_context: str) -> dict:
        """
        Store raw context and extract contact info + skills via regex/taxonomy.
        No LLM calls — gap analysis happens separately via analyze_gaps.
        """
        import re

        profile = await self.get_or_create(campaign_id, user_id)

        # ── Store raw context (append if new content) ────────────────────────
        if profile.raw_context and raw_context not in profile.raw_context:
            profile.raw_context = profile.raw_context + "\n\n" + raw_context
        else:
            profile.raw_context = raw_context

        # ── Contact info (regex — reliable on any format) ────────────────────
        _EMAIL    = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}')
        _PHONE    = re.compile(r'\+?[\d][\d\s\-().]{7,}')
        _LINKEDIN = re.compile(r'linkedin\.com/in/[\w-]+', re.I)
        _GITHUB   = re.compile(r'github\.com/[\w-]+', re.I)
        _PORTFOLIO= re.compile(r'\*\*Portfolio:\*\*\s*([^\s\n]+)', re.I)
        _YEARS    = re.compile(r'(\d+)\+?\s*years?\s*of\s*(?:professional\s*)?experience', re.I)

        m = _EMAIL.search(raw_context)
        if m and not profile.email:
            profile.email = m.group()

        m = _PHONE.search(raw_context)
        if m:
            raw_phone = m.group().strip()
            if sum(c.isdigit() for c in raw_phone) >= 7 and not profile.phone:
                profile.phone = raw_phone

        m = _LINKEDIN.search(raw_context)
        if m and not profile.linkedin_url:
            profile.linkedin_url = m.group()

        m = _GITHUB.search(raw_context)
        if m and not profile.github_url:
            profile.github_url = m.group()

        m = _PORTFOLIO.search(raw_context)
        if m and not profile.portfolio_url:
            profile.portfolio_url = m.group(1).strip()

        m = _YEARS.search(raw_context)
        if m and profile.years_of_experience is None:
            try:
                profile.years_of_experience = int(m.group(1))
            except (ValueError, TypeError):
                pass

        # ── Name (markdown H1 or "# CV -- Name" pattern) ────────────────────
        if not profile.full_name:
            m = re.search(r'^#\s+(?:CV\s+[-–—]+\s*)?(.+)', raw_context, re.M)
            if m:
                candidate = m.group(1).strip()
                if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z'\-]+)+$", candidate):
                    profile.full_name = candidate

        # ── Location ("**Location:** City, Country") ─────────────────────────
        if not profile.city:
            m = re.search(r'\*\*Location:\*\*\s*(.+)', raw_context)
            if m:
                parts = [p.strip() for p in m.group(1).split(',')]
                profile.city = parts[0]
                if len(parts) >= 2 and not profile.country:
                    profile.country = parts[1]

        # ── Skills taxonomy scan ─────────────────────────────────────────────
        from app.services.job_hunter.extractor import _skills as _scan_skills
        found_skills = _scan_skills(raw_context)
        if found_skills:
            existing = set(profile.skills or [])
            profile.skills = list(existing | set(found_skills))

        profile.updated_at = utcnow()
        await self.db.commit()

        return {"status": "stored"}
