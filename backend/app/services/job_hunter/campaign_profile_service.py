# backend/app/services/job_hunter/campaign_profile_service.py
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import CampaignProfile, JobHunterCampaign
from app.core.config import settings
from app.services.job_hunter.llm import call_llm

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

    async def _call_haiku(self, prompt: str, max_tokens: int = 1000) -> str:
        return await call_llm(prompt, max_tokens)

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
        AI reviews current profile data against the campaign category.
        Returns:
          - gaps: list of specific missing/weak items
          - questions: targeted questions to fill each gap
          - is_ready: bool — can we generate a strong resume right now?
          - score: 0-100 readiness score
        """
        profile = await self.get_or_create(campaign_id, user_id)

        # Get campaign category for context
        camp_result = await self.db.execute(
            select(JobHunterCampaign).where(JobHunterCampaign.id == campaign_id)
        )
        campaign = camp_result.scalar_one_or_none()
        category = campaign.broad_category if campaign else "Software Engineering"
        anywhere = bool(campaign.anywhere) if campaign else False
        work_type = campaign.work_type if campaign else "remote"

        # Build a summary of what we have
        exp = profile.work_experience or []
        exp_summary = []
        for job in exp:
            resp = job.get("responsibilities", [])
            bullet_count = len(resp) if isinstance(resp, list) else len([r for r in str(resp).split("\n") if r.strip()])
            has_dates = bool(job.get("start_date")) and bool(job.get("end_date") or job.get("current"))
            exp_summary.append({
                "title": job.get("title", "Unknown"),
                "company": job.get("company", "Unknown"),
                "has_dates": has_dates,
                "bullet_count": bullet_count,
            })

        # Location is only required if the campaign is NOT set to "anywhere"
        location_ok = anywhere or (bool(profile.city) or bool(profile.country))

        profile_snapshot = {
            "has_name": bool(profile.full_name),
            "has_email": bool(profile.email),
            "has_phone": bool(profile.phone),
            "has_location": location_ok,
            "location_note": "campaign is set to 'anywhere' — location not required" if anywhere else None,
            "has_linkedin": bool(profile.linkedin_url),
            "has_github": bool(profile.github_url),
            "skill_count": len(profile.skills or []),
            "experience_count": len(exp),
            "experience_detail": exp_summary,
            "education_count": len(profile.education or []),
            "project_count": len(profile.projects or []),
            "achievement_count": len(profile.achievements or []),
            "has_raw_context": bool(profile.raw_context),
            "raw_context_length": len(profile.raw_context or ""),
            "has_years_of_experience": profile.years_of_experience is not None,
            "work_type": work_type,
        }

        raw = await self._call_haiku(
            f"You are a professional resume consultant reviewing a candidate's profile for a {category} campaign.\n\n"
            f"Current profile state:\n{json.dumps(profile_snapshot, indent=2)}\n\n"
            f"Evaluate the profile and respond with a JSON object in this exact format:\n"
            f'{{\n'
            f'  "score": <0-100 integer>,\n'
            f'  "is_ready": <true if score >= 70>,\n'
            f'  "gaps": [\n'
            f'    "specific gap description 1",\n'
            f'    "specific gap description 2"\n'
            f'  ],\n'
            f'  "questions": [\n'
            f'    {{"gap": "gap description", "question": "specific question to ask the candidate"}}\n'
            f'  ],\n'
            f'  "summary": "one sentence overall assessment"\n'
            f'}}\n\n'
            f"Rules for scoring:\n"
            f"- Deduct 20pts if no work experience\n"
            f"- Deduct 15pts if has_years_of_experience is false (this is required — ask for it)\n"
            f"- Deduct 10pts per job missing start/end dates\n"
            f"- Deduct 5pts per job with fewer than 4 bullet points\n"
            f"- Deduct 15pts if fewer than 5 skills\n"
            f"- Deduct 10pts if no contact info (name/email/phone)\n"
            f"- Deduct 10pts if no achievements/impact statements\n"
            f"- Deduct 5pts if no LinkedIn URL\n"
            f"- Add 10pts if raw_context_length > 500 (rich context provided)\n"
            f"NEVER flag high skill counts as a problem — the system filters skills per job automatically.\n"
            f"NEVER flag raw_context_length as a problem if work_experience and skills are present.\n"
            f"Only flag things that would actually prevent generating a strong resume.\n"
            f"IMPORTANT: If has_years_of_experience is false, you MUST include a question asking "
            f"'How many total years of professional experience do you have?' in the questions array.\n"
            f"If any job is missing dates, ask for the start and end dates for that specific job.\n"
            f"Return only the JSON object, no other text.",
            max_tokens=800,
        )

        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {"score": 0, "is_ready": False, "gaps": ["Could not analyze profile"], "questions": [], "summary": "Analysis failed"}
        try:
            result = json.loads(raw[start:end])
            # Persist gaps back to profile
            profile.completion_gaps = result.get("gaps", [])
            profile.is_complete = result.get("is_ready", False)
            await self.db.commit()
            return result
        except json.JSONDecodeError:
            return {"score": 0, "is_ready": False, "gaps": ["Could not parse AI response"], "questions": [], "summary": "Analysis failed"}

    async def process_raw_context(self, campaign_id: str, user_id: str, raw_context: str) -> dict:
        """
        User dumps free-form text about themselves (copy-paste from old CV, LinkedIn, etc).
        AI extracts structured data and merges into the profile.
        Returns the extracted fields + updated gaps.
        """
        # Use Gemini 2.0 Flash (free) — handles large structured extraction well
        prompt = (
            "Extract structured resume data from the raw text below. "
            "Return ONLY a valid JSON object — no markdown, no explanation.\n\n"
            "Schema (omit fields you cannot find — do not invent values):\n"
            '{\n'
            '  "full_name": "string",\n'
            '  "email": "string",\n'
            '  "phone": "string",\n'
            '  "city": "string",\n'
            '  "country": "string",\n'
            '  "linkedin_url": "string",\n'
            '  "github_url": "string",\n'
            '  "portfolio_url": "string",\n'
            '  "skills": ["skill1", "skill2", "...all skills found"],\n'
            '  "work_experience": [\n'
            '    {\n'
            '      "title": "Job Title",\n'
            '      "company": "Company Name",\n'
            '      "location": "City, Country or null",\n'
            '      "start_date": "MMM YYYY or YYYY",\n'
            '      "end_date": "MMM YYYY or Present",\n'
            '      "responsibilities": ["every bullet point verbatim"]\n'
            '    }\n'
            '  ],\n'
            '  "education": [\n'
            '    {\n'
            '      "degree": "Degree name",\n'
            '      "field_of_study": "Field",\n'
            '      "institution": "School name",\n'
            '      "graduation_year": "YYYY or null",\n'
            '      "is_certification": false\n'
            '    }\n'
            '  ],\n'
            '  "certifications": [\n'
            '    {\n'
            '      "degree": "Certification name",\n'
            '      "institution": "Issuer",\n'
            '      "is_certification": true\n'
            '    }\n'
            '  ],\n'
            '  "projects": [\n'
            '    {\n'
            '      "name": "Project name",\n'
            '      "description": "What it does",\n'
            '      "tech_stack": ["tech1"],\n'
            '      "link": "url or null"\n'
            '    }\n'
            '  ],\n'
            '  "achievements": ["quantified impact statement 1", "..."],\n'
            '  "years_of_experience": <integer — extract from text like "6+ years", "senior with 8 years", etc. null if not stated>\n'
            '}\n\n'
            f"Raw text:\n{raw_context}\n\n"
            "Return only the JSON object. Include ALL skills found. Include ALL work experience entries. "
            "Do not truncate arrays."
        )

        try:
            raw = (await call_llm(prompt, max_tokens=4000)).strip()
        except Exception:
            logger.exception("process_raw_context: LLM call failed")
            return {"extracted": {}, "message": "AI extraction failed"}

        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {"extracted": {}, "message": "Could not extract structured data"}

        try:
            extracted = json.loads(raw[start:end])
        except json.JSONDecodeError:
            return {"extracted": {}, "message": "Could not parse extraction"}

        # Merge extracted data into profile (non-null values only)
        profile = await self.get_or_create(campaign_id, user_id)
        # Append to existing raw_context rather than replace — preserves original resume text
        if profile.raw_context and raw_context not in profile.raw_context:
            profile.raw_context = profile.raw_context + "\n\n" + raw_context
        else:
            profile.raw_context = raw_context

        for field in ["full_name", "email", "phone", "city", "country", "linkedin_url", "github_url", "portfolio_url"]:
            val = extracted.get(field)
            if val:
                setattr(profile, field, val)

        if extracted.get("years_of_experience") and profile.years_of_experience is None:
            try:
                profile.years_of_experience = int(extracted["years_of_experience"])
            except (ValueError, TypeError):
                pass

        # For lists: merge not replace (deduplicate skills)
        if extracted.get("skills"):
            existing = set(profile.skills or [])
            profile.skills = list(existing | set(extracted["skills"]))

        if extracted.get("work_experience"):
            profile.work_experience = extracted["work_experience"]

        if extracted.get("education") or extracted.get("certifications"):
            edu = extracted.get("education") or []
            certs = extracted.get("certifications") or []
            profile.education = edu + certs

        if extracted.get("projects"):
            profile.projects = extracted["projects"]

        if extracted.get("achievements"):
            existing_ach = set(profile.achievements or [])
            profile.achievements = list(existing_ach | set(extracted["achievements"]))

        profile.updated_at = utcnow()
        await self.db.commit()

        # Re-analyze gaps after extraction
        gaps_result = await self.analyze_gaps(campaign_id, user_id)
        return {"extracted": extracted, "gaps": gaps_result}
