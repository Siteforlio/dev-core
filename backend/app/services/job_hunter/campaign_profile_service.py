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
    # Technology
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
    "IT Support / Sysadmin",
    "Blockchain / Web3",
    "Game Development",
    "Embedded Systems",
    # Business & Finance
    "Accounting",
    "Finance / Investment",
    "Banking",
    "Financial Analysis",
    "Auditing",
    "Tax & Compliance",
    "Business Analysis",
    "Strategy & Consulting",
    "Operations Management",
    "Project Management",
    "Supply Chain / Logistics",
    "Procurement",
    # Marketing & Sales
    "Digital Marketing",
    "Content Marketing",
    "SEO / SEM",
    "Social Media Management",
    "Brand Management",
    "Growth Marketing",
    "Sales",
    "Business Development",
    "Account Management",
    "Customer Success",
    "Public Relations",
    "Copywriting",
    # Design & Creative
    "Graphic Design",
    "Motion Design / Animation",
    "Video Production",
    "Photography",
    "Architecture",
    "Interior Design",
    "Fashion Design",
    "Industrial Design",
    "Creative Direction",
    # Healthcare & Medical
    "Medicine / Clinical",
    "Nursing",
    "Pharmacy",
    "Dentistry",
    "Mental Health / Counseling",
    "Public Health",
    "Biomedical Engineering",
    "Medical Research",
    "Healthcare Administration",
    "Physical Therapy",
    "Nutrition / Dietetics",
    # Legal
    "Law / Legal Practice",
    "Paralegal",
    "Compliance & Regulatory",
    "IP & Patents",
    "Corporate Law",
    # Education & Research
    "Teaching / Instruction",
    "Academic Research",
    "Curriculum Development",
    "Training & L&D",
    "EdTech",
    "Library Science",
    # Engineering (Non-Software)
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical Engineering",
    "Chemical Engineering",
    "Aerospace Engineering",
    "Environmental Engineering",
    "Structural Engineering",
    "Manufacturing Engineering",
    # Science & Research
    "Biology / Life Sciences",
    "Chemistry",
    "Physics",
    "Environmental Science",
    "Materials Science",
    "Data Analysis / Statistics",
    # Human Resources
    "HR Management",
    "Talent Acquisition / Recruiting",
    "Compensation & Benefits",
    "HR Business Partner",
    "Organizational Development",
    # Operations & Support
    "Customer Support",
    "Administrative Assistant",
    "Office Management",
    "Executive Assistant",
    "Operations Analyst",
    # Trades & Construction
    "Construction Management",
    "Electrical Trade",
    "Plumbing",
    "HVAC",
    "Carpentry",
    "Civil Works",
    # Hospitality & Tourism
    "Hotel Management",
    "Event Planning",
    "Travel & Tourism",
    "Food & Beverage",
    "Restaurant Management",
    # Media & Communications
    "Journalism",
    "Broadcasting",
    "Editing / Publishing",
    "Communications",
    "Translation / Localization",
    # Agriculture & Environment
    "Agriculture / Agronomy",
    "Veterinary",
    "Forestry",
    "Environmental Management",
    # Government & Social
    "Government / Public Sector",
    "Non-profit / NGO",
    "Social Work",
    "Policy & Advocacy",
    "International Development",
    # Other
    "Real Estate",
    "Insurance",
    "Logistics / Freight",
    "Transportation",
    "Security Services",
    "Sports & Fitness",
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
            f"You are reviewing a job candidate's profile for a {role_context} position.\n\n"
            f"Below is the candidate's raw profile context (exactly what they submitted):\n"
            f"---\n{context_for_llm}\n---\n\n"
            f"Quick extracted facts:\n{quick_facts}\n\n"
            f"Evaluate whether this candidate has provided enough information to be matched to relevant "
            f"{role_context} job listings and to have a strong application submitted on their behalf.\n"
            f"This tool is used by people across ALL industries — not just tech. Evaluate based on "
            f"what matters for their specific field ({role_context}), not on software engineering standards.\n\n"
            f"Respond with a JSON object:\n"
            f'{{\n'
            f'  "score": <0-100 integer>,\n'
            f'  "is_ready": <true if score >= 70>,\n'
            f'  "gaps": ["specific missing info relevant to {role_context} — e.g. no work history, no key skills listed, no contact info"],\n'
            f'  "questions": [{{"gap": "gap label", "question": "simple, friendly question to fill this gap"}}],\n'
            f'  "summary": "one sentence: what they have + what would strengthen their profile"\n'
            f'}}\n\n'
            f"SCORING (start at 100, deduct for what's missing):\n"
            f"- -25 if no work/experience history described at all (no roles, no projects, no field context)\n"
            f"- -15 if no relevant skills, tools, or qualifications for {role_context} are mentioned\n"
            f"- -15 if no contact info at all (name, email, or phone)\n"
            f"- -10 if experience is described but extremely vague (just titles, no context or outcomes)\n"
            f"- -10 if years of experience or career level is completely unclear\n"
            f"- -5  if no indication of preferred location or remote/onsite preference\n"
            f"- +10 if they have clear, specific experience directly relevant to {role_context}\n"
            f"- +5  if they mention specific tools, credentials, or certifications relevant to {role_context}\n\n"
            f"IMPORTANT: Adapt expectations to the field. A nurse doesn't need GitHub. "
            f"A carpenter doesn't need LinkedIn. A fresh graduate shouldn't be penalized for short history. "
            f"Ask ONLY for information that would genuinely help match or apply for {role_context} jobs. "
            f"NEVER ask for info that's already present. Keep questions friendly and conversational.\n"
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
