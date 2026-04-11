import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import AsyncAnthropic
from app.models.pg.job_hunter import JobHunterProfile
from app.core.config import settings

REQUIRED_FIELDS = {
    "full_name": "Contact: full name",
    "email": "Contact: email",
    "phone": "Contact: phone",
    "city": "Contact: city",
    "country": "Contact: country",
    "linkedin_url": "Contact: LinkedIn URL",
    "github_url": "Contact: GitHub URL",
    "work_experience": "Work experience (min 1 entry)",
    "education": "Education (min 1 entry)",
    "skills": "Skills (min 3)",
    "projects": "Projects (min 1 entry)",
    "languages_spoken": "Languages spoken (min 1)",
}


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def check_completeness(self, data: dict) -> dict:
        missing = []
        for field, label in REQUIRED_FIELDS.items():
            value = data.get(field)
            if not value:
                missing.append(field)
            elif field == "skills" and isinstance(value, list) and len(value) < 3:
                missing.append(field)
        score = int((1 - len(missing) / len(REQUIRED_FIELDS)) * 100)
        return {"is_complete": len(missing) == 0, "missing": missing, "completion_score": score}

    async def parse_resume_text(self, text: str) -> dict:
        """Extract structured profile fields from raw resume text using Haiku."""
        message = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": (
                    "Extract structured resume data as JSON with keys: full_name, email, phone, "
                    "city, country, linkedin_url, github_url, work_experience (list), education (list), "
                    "skills (list of strings), projects (list), languages_spoken (list). Resume text:\n\n"
                    + text
                ),
            }],
        )
        text_content = message.content[0].text
        try:
            start = text_content.find("{")
            end = text_content.rfind("}") + 1
            if start == -1 or end == 0:
                return {}
            return json.loads(text_content[start:end])
        except json.JSONDecodeError:
            return {}

    async def upsert_profile(self, user_id: str, data: dict) -> JobHunterProfile:
        result = await self.db.execute(
            select(JobHunterProfile).where(JobHunterProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        completeness = self.check_completeness(data)
        if not profile:
            profile = JobHunterProfile(
                id=str(uuid.uuid4()),
                user_id=user_id,
                is_complete=completeness["is_complete"],
                completion_score=completeness["completion_score"],
                full_name=data.get("full_name"),
                email=data.get("email"),
                phone=data.get("phone"),
                city=data.get("city"),
                country=data.get("country"),
                work_experience=data.get("work_experience", []),
                education=data.get("education", []),
                skills=data.get("skills", []),
                projects=data.get("projects", []),
                languages_spoken=data.get("languages_spoken", []),
                github_url=data.get("github_url"),
                linkedin_url=data.get("linkedin_url"),
                portfolio_url=data.get("portfolio_url"),
            )
            self.db.add(profile)
        else:
            for field in ["work_experience", "education", "skills", "projects", "languages_spoken"]:
                if data.get(field) is not None:
                    setattr(profile, field, data[field])
            for field in ["full_name", "email", "phone", "city", "country", "linkedin_url", "github_url", "portfolio_url"]:
                if data.get(field) is not None:
                    setattr(profile, field, data[field])
            profile.is_complete = completeness["is_complete"]
            profile.completion_score = completeness["completion_score"]
        await self.db.commit()
        return profile
