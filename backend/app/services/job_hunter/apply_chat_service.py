"""
ApplyChatService — job-scoped AI chat + cover letter generation.

Each instance is tied to a DB session. Two public methods:
  - generate_cover_letter(app, listing) → str
  - chat(application, listing, user_message, history) → str

System context injected into every call:
  - Full job description
  - Candidate profile (work experience, skills, education, projects)
  - Tailored resume text (if present in form_answers)
"""
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pg.job_hunter import Application, JobListing, JobHunterProfile
from app.services.job_hunter.llm import call_llm

logger = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_experience(items: list) -> str:
    if not items:
        return "None listed."
    lines = []
    for e in items:
        title = e.get("title") or e.get("role", "")
        company = e.get("company", "")
        start = e.get("start_date") or e.get("start", "")
        end = e.get("end_date") or e.get("end", "present")
        desc = e.get("description") or e.get("responsibilities") or ""
        lines.append(f"  • {title} @ {company} ({start}–{end}): {desc}")
    return "\n".join(lines)


def _fmt_skills(items: list) -> str:
    if not items:
        return "None listed."
    if items and isinstance(items[0], dict):
        return ", ".join(i.get("name", str(i)) for i in items)
    return ", ".join(str(i) for i in items)


def _fmt_education(items: list) -> str:
    if not items:
        return "None listed."
    lines = []
    for e in items:
        degree = e.get("degree", "")
        institution = e.get("institution") or e.get("school", "")
        year = e.get("year") or e.get("end_date", "")
        lines.append(f"  • {degree}, {institution} ({year})")
    return "\n".join(lines)


def _build_system_context(profile: JobHunterProfile | None, listing: JobListing, app: Application) -> str:
    candidate_name = profile.full_name if profile else "the candidate"

    profile_block = ""
    if profile:
        profile_block = f"""
CANDIDATE PROFILE:
Name: {profile.full_name or "N/A"}
Email: {profile.email or "N/A"}
Phone: {profile.phone or "N/A"}
Location: {profile.city or ""}, {profile.country or ""}
LinkedIn: {profile.linkedin_url or "N/A"}
GitHub: {profile.github_url or "N/A"}

Work Experience:
{_fmt_experience(profile.work_experience or [])}

Education:
{_fmt_education(profile.education or [])}

Skills: {_fmt_skills(profile.skills or [])}
""".strip()
    else:
        profile_block = "CANDIDATE PROFILE: Not available."

    job_description = listing.description or "Job description not available."

    tailored_text = ""
    if app.form_answers:
        tailored_text = app.form_answers.get("tailored_resume_text", "")

    cover_letter_block = ""
    if app.cover_letter:
        cover_letter_block = f"\nCURRENT COVER LETTER:\n{app.cover_letter}\n"

    tailored_block = ""
    if tailored_text:
        tailored_block = "TAILORED RESUME SUMMARY:\n" + tailored_text[:1500]

    return f"""You ARE {candidate_name}. You are responding to questions during a job application process — answer entirely in first person, as yourself. Never refer to yourself in the third person. Never say "the candidate" or use your own name to describe yourself.

TARGET ROLE: {listing.title} at {listing.company}
LOCATION: {listing.location or "Not specified"}

JOB DESCRIPTION:
{job_description[:3000]}

YOUR BACKGROUND:
{profile_block}
{cover_letter_block}
{tailored_block}

When answering questions about yourself, your experience, skills, or motivations — draw on your actual background above and respond naturally in first person. Be concise, honest, and specific. Do not fabricate experience you don't have."""


# ── service ───────────────────────────────────────────────────────────────────

class ApplyChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_profile(self, user_id: str) -> JobHunterProfile | None:
        result = await self.db.execute(
            select(JobHunterProfile).where(JobHunterProfile.user_id == user_id, JobHunterProfile.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def generate_cover_letter(self, app: Application, listing: JobListing) -> str:
        """Generate a tailored cover letter for this application."""
        profile = await self._get_profile(app.user_id)
        system_ctx = _build_system_context(profile, listing, app)

        candidate_name = profile.full_name if profile else "the candidate"

        prompt = f"""{system_ctx}

---

Write a professional cover letter for {candidate_name} applying to {listing.title} at {listing.company}.

Requirements:
- 3–4 short paragraphs
- Opening: why this specific company/role excites them
- Middle: 2-3 most relevant accomplishments from their experience, with concrete details
- Closing: confident call to action
- Tone: professional but human — not generic, not sycophantic
- Length: 250–350 words
- Do NOT include date, address blocks, or "Dear Hiring Manager" boilerplate — start directly with the opening paragraph

Write only the cover letter body. No commentary."""

        result = await call_llm(prompt, max_tokens=600)
        return result.strip()

    async def generate_form_answers(
        self,
        application: Application,
        listing: JobListing,
        fields: list[dict],
    ) -> dict[str, str]:
        """
        Given a list of form fields scraped from a live ATS page, generate answers
        for each field using the candidate's profile and job context.

        fields: [{"label": str, "type": str, "options": list[str] | None}]
        Returns: {"field_label": "answer", ...}
        """
        import uuid
        from datetime import datetime, timezone
        from sqlalchemy.orm import flag_modified

        profile = await self._get_profile(application.user_id)
        system_ctx = _build_system_context(profile, listing, application)

        fields_json = json.dumps(fields, ensure_ascii=False, indent=2)

        prompt = f"""{system_ctx}

---

You are filling a job application form. Below are the exact fields on this form.
For each field, provide the best answer based on the candidate profile above.
Return a valid JSON object where keys are the exact field labels and values are the answers.

FORM FIELDS:
{fields_json}

Rules:
- For select/radio: return exactly one of the option strings listed
- For checkbox: return "true" or "false"
- For file inputs: return "__RESUME__" (handled separately)
- Be truthful — only use information from the candidate profile above
- Be concise for text/select fields, thorough for textarea fields
- If you genuinely cannot answer a field from the profile, return ""

Return only the JSON object, no commentary."""

        result = await call_llm(prompt, max_tokens=1000, json_mode=True)

        try:
            answers = json.loads(result) if result else {}
        except (json.JSONDecodeError, Exception):
            answers = {}

        # Build chat_log entries
        now = datetime.now(timezone.utc).isoformat()
        user_entry = {
            "id": str(uuid.uuid4()),
            "source": "extension",
            "role": "user",
            "content": f"Filling form — {len(fields)} fields: [{', '.join(f['label'] for f in fields)}]",
            "timestamp": now,
        }
        assistant_entry = {
            "id": str(uuid.uuid4()),
            "source": "extension",
            "role": "assistant",
            "content": json.dumps(answers, ensure_ascii=False),
            "timestamp": now,
        }

        # Append to chat_log safely (flag_modified required for JSONB mutation detection)
        current_log = list(application.chat_log or [])
        current_log.append(user_entry)
        current_log.append(assistant_entry)
        application.chat_log = current_log
        flag_modified(application, "chat_log")
        await self.db.commit()

        return answers

    async def chat(
        self,
        application: Application,
        listing: JobListing,
        user_message: str,
        history: list[dict],
    ) -> str:
        """Job-scoped conversational AI. History is list of {role, content} dicts."""
        profile = await self._get_profile(application.user_id)
        system_ctx = _build_system_context(profile, listing, application)

        # Build conversation thread
        history_text = ""
        for msg in history[-10:]:  # keep last 10 turns to avoid token bloat
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"\n{role_label}: {msg['content']}"

        prompt = f"""{system_ctx}

---
CONVERSATION SO FAR:{history_text}

User: {user_message}
Assistant:"""

        result = await call_llm(prompt, max_tokens=500)
        return result.strip()
