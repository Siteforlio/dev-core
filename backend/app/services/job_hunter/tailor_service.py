# backend/app/services/job_hunter/tailor_service.py
import json
import uuid
import asyncio
import time
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import JobListing, CampaignProfile, Application
from app.core.config import settings
from app.services.job_hunter.llm import call_llm
from app.services.job_hunter.matcher_service import matcher

RESUMES_BASE = Path(__file__).parent.parent.parent.parent / "resumes"
RESUMES_BASE.mkdir(exist_ok=True)
# Keep legacy alias so any existing references still resolve
RESUMES_DIR = RESUMES_BASE

# Semaphore is created lazily per event loop to avoid "bound to a different event loop"
# errors when Celery re-uses the same process across multiple asyncio.run() calls.
_HAIKU_SEM: asyncio.Semaphore | None = None


def _get_haiku_sem() -> asyncio.Semaphore:
    global _HAIKU_SEM
    loop = asyncio.get_event_loop()
    if _HAIKU_SEM is None or _HAIKU_SEM._loop is not loop:
        _HAIKU_SEM = asyncio.Semaphore(4)
    return _HAIKU_SEM


def _build_immutable_facts(profile, experience: list[dict]) -> str:
    """
    Build the IMMUTABLE FACTS block that is injected into every LLM prompt.

    These three things NEVER change regardless of the target role:
      1. Education — degrees, institutions, years, certifications
      2. Previous employers — exact company names as they appear in the profile
      3. Candidate location — city and country as entered by the user

    Any LLM prompt that includes this block must treat these facts as read-only.
    """
    lines = ["IMMUTABLE FACTS (DO NOT change, rewrite, omit, or invent alternatives):"]

    # 1. Education
    edu = getattr(profile, "education", None) or []
    if edu:
        edu_strs = []
        for e in edu:
            degree = e.get("degree", "")
            field  = e.get("field_of_study", "")
            inst   = e.get("institution", "")
            year   = e.get("graduation_year", "")
            entry  = degree
            if field:
                entry += f" in {field}"
            if inst:
                entry += f" — {inst}"
            if year:
                entry += f" ({year})"
            if entry.strip():
                edu_strs.append(entry.strip())
        if edu_strs:
            lines.append(f"  Education: {' | '.join(edu_strs)}")

    # 2. Previous employers — exact names, never paraphrased
    companies = []
    for job in experience:
        name = (job.get("company") or "").strip()
        if name and name not in companies:
            companies.append(name)
    if companies:
        lines.append(f"  Previous employers (exact names): {', '.join(companies)}")

    # 3. Location
    city    = (getattr(profile, "city", None) or "").strip()
    country = (getattr(profile, "country", None) or "").strip()
    loc = ", ".join(filter(None, [city, country]))
    if loc:
        lines.append(f"  Location: {loc}")

    lines.append(
        "RULE: Every output must preserve the above facts exactly. "
        "Do not rename companies, move the location, alter degree titles, or remove education."
    )
    return "\n".join(lines)


class TailorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _call_haiku(self, prompt: str, max_tokens: int = 1000, quality: bool = False) -> str:
        import logging as _log
        async with _get_haiku_sem():
            result = await call_llm(prompt, max_tokens, quality=quality)
            if not result and quality:
                # Pro model returned empty — fall back to Flash
                _log.getLogger(__name__).warning(
                    "_call_haiku: Pro model returned empty, retrying with Flash"
                )
                result = await call_llm(prompt, max_tokens, quality=False)
            return result

    async def extract_keywords(self, jd: str) -> list[str]:
        raw = await self._call_haiku(
            f"Extract all important ATS keywords from this job description. "
            f"Include every role-specific skill, tool, platform, domain knowledge term, "
            f"and competency the employer is clearly screening for. "
            f"Only include terms that genuinely appear or are strongly implied by the JD — "
            f"do not pad with generic words. Quality over quantity. "
            f"Return a JSON array of strings only, no explanation.\n\n{jd[:10000]}"
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return []

    async def _tailor_all(
        self,
        profile,
        experience: list[dict],
        projects: list[dict],
        jd: str,
        target_role: str,
        target_company: str,
        immutable_facts: str,
        bullets: list[str],
    ) -> dict:
        """
        Single Pro model call that replaces all individual LLM steps:
          - keyword extraction
          - positioning brief (narrative + skills)
          - professional summary
          - bullet rewrites
          - project description rewrites

        Returns a dict with keys:
          keywords, positioning_narrative, positioning_skills,
          summary, rewritten_bullets, rewritten_projects
        """
        exp_titles = "; ".join(
            f"{j.get('title','')} at {j.get('company','')}" for j in experience[:5] if j.get("title")
        )
        raw_ctx = (getattr(profile, "raw_context", None) or "")[:2500]
        profile_skills = ", ".join((profile.skills or [])[:20])
        years = getattr(profile, "years_of_experience", None) or len(experience)

        bullets_json = json.dumps(bullets[:20])
        projects_json = json.dumps([
            {"name": p.get("name",""), "description": p.get("description",""), "tech_stack": p.get("tech_stack",[])}
            for p in projects
        ])

        prompt = (
            f"You are a senior career strategist. Complete all sections below for a resume tailoring job. "
            f"Return a SINGLE valid JSON object with exactly these keys.\n\n"
            f"TARGET ROLE: {target_role} at {target_company}\n\n"
            f"CANDIDATE:\n"
            f"  Years experience: {years}\n"
            f"  Titles: {exp_titles}\n"
            f"  Skills: {profile_skills}\n"
            f"  Profile text: {raw_ctx}\n\n"
            f"JOB DESCRIPTION:\n{jd[:4000]}\n\n"
            f"{immutable_facts}\n\n"
            f"BULLETS TO REWRITE:\n{bullets_json}\n\n"
            f"PROJECTS TO REWRITE:\n{projects_json}\n\n"
            f"OUTPUT FORMAT — return this exact JSON structure:\n"
            f'{{\n'
            f'  "keywords": ["array of 15-25 ATS keywords from the JD"],\n'
            f'  "positioning_narrative": "2-3 sentences: genuine credibility hooks between this candidate and this role",\n'
            f'  "positioning_skills": ["10-15 SHORT skill names 1-4 words each, in target role language"],\n'
            f'  "summary": "2 sentences: punchy value proposition for THIS role. Sentence 1: who they are + what they bring. Sentence 2: top 1-2 strengths for this role.",\n'
            f'  "rewritten_bullets": ["same length array as input bullets — rewritten for this role, domain-translated, strong verbs, no justification tails"],\n'
            f'  "rewritten_projects": [{{"name": "...", "description": "1-2 sentences angled at this role — lead with the aspect the HM cares about"}}]\n'
            f'}}\n\n'
            f"RULES (apply to all sections):\n"
            f"- NEVER invent achievements, companies, degrees, or metrics not in the profile\n"
            f"- DO translate domain language to match the target role's vocabulary\n"
            f"- Bullets: keep all numbers/scale, use strong verbs, NO 'directly applicable to...' tails\n"
            f"- Skills: 1-4 words max each, no verbose descriptions\n"
            f"- Summary: specific to this role, no generic filler, reference actual profile metrics\n"
            f"- Projects: only re-angle what actually exists — never add fictional integrations\n"
            f"- Return ONLY valid JSON, no markdown, no explanation"
        )

        raw = await self._call_haiku(prompt, max_tokens=3000, quality=True)

        # Extract JSON — handle markdown code fences
        import re as _re
        raw = _re.sub(r"```(?:json)?", "", raw).strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {}
        try:
            return json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            return {}

    def pick_top_competencies(self, jd_text: str, skills: list[str]) -> list[str]:
        """
        Pick the 8 skills most relevant to this JD using local sentence-transformers.
        Zero API calls. Falls back to skills[:8] if the model is unavailable.
        """
        return matcher.match_skills(jd_text, skills, top_n=8)

    def pick_resume_skills(self, jd_text: str, skills: list[str]) -> list[str]:
        """
        Pick up to 20 skills for the resume using local sentence-transformers.
        Zero API calls. Falls back to skills[:20] if the model is unavailable.
        """
        return matcher.match_skills(jd_text, skills, top_n=20)

    async def rewrite_bullets(
        self,
        bullets: list[str],
        keywords: list[str],
        target_role: str = "",
        target_company: str = "",
        jd_summary: str = "",
        immutable_facts: str = "",
    ) -> list[str]:
        """
        Rewrite resume bullets with domain translation.

        The core idea: keep every real achievement (numbers, scale, outcomes)
        but reframe the *context* so it reads naturally for the target role.
        A doctor applying for a mechanic job should say "diagnosed and resolved
        200 engine failures" not "treated 200 patients" — the achievement is
        the same, the language fits the new domain.

        Rules enforced in the prompt:
          - Numbers and scale are SACRED — never change them
          - Domain language IS changed to match the target role
          - JD keywords are woven in naturally
          - Every bullet ends with a measurable outcome
        """
        if not bullets:
            return []

        domain_context = ""
        if target_role or target_company:
            domain_context = f"TARGET ROLE: {target_role}"
            if target_company:
                domain_context += f" at {target_company}"
        if jd_summary:
            domain_context += f"\nROLE CONTEXT: {jd_summary[:2500]}"

        raw = await self._call_haiku(
            f"You are a senior career strategist rewriting resume bullets for a career pivot or cross-domain application.\n\n"
            f"{domain_context}\n\n"
            f"{immutable_facts}\n\n"
            f"TASK: For each bullet, extract the underlying achievement (scale, impact, outcome, numbers) "
            f"and retell it in the language of the target role. "
            f"The achievement is real and belongs to the candidate — your job is to frame it "
            f"so a hiring manager in the TARGET field immediately recognises its relevance.\n\n"
            f"CROSS-DOMAIN TRANSLATION PRINCIPLE:\n"
            f"Think about WHAT the candidate actually did (built systems, led teams, managed complexity, "
            f"drove adoption, closed deals, coordinated stakeholders) and express it in the vocabulary "
            f"the target role uses. The domain changes; the proof of capability does not.\n\n"
            f"EXAMPLES:\n"
            f'  Tech → Philanthropy/Partnerships: "Built platform connecting 55M users to 17,000 providers"'
            f' → "Architected ecosystem connecting 55M+ Kenyans to 17,000+ service providers, '
            f'demonstrating large-scale stakeholder network development"\n'
            f'  Tech → Philanthropy: "Integrated payment processing with escrow and compliance"'
            f' → "Designed compliant financial flows and managed multi-party transaction structures '
            f'across Kenya\'s financial ecosystem"\n\n'
            f"RULES:\n"
            f"- NEVER change the numbers or scale (if original says 55M, keep 55M)\n"
            f"- NEVER invent achievements, roles, or domain experience that don't exist in the original\n"
            f"- DO fully translate domain language — remove tech jargon, use the target field's vocabulary\n"
            f"- Use strong ownership verbs: Led, Architected, Drove, Mobilised, Cultivated, Negotiated, Secured, Built\n"
            f"- Naturally weave in these JD keywords where they fit: {', '.join(keywords[:20])}\n"
            f"- Every bullet MUST show tangible impact (scale, reach, outcome, or stakeholder value)\n"
            f"- NEVER add commentary or justification tails. Do NOT end bullets with phrases like "
            f"'directly applicable to...', 'directly parallels...', 'directly mirroring...', "
            f"'translates directly to...', or any explanation of relevance. "
            f"The bullet must stand alone — let the achievement speak for itself.\n"
            f"- Return a JSON array of rewritten bullet strings only, no explanation\n\n"
            f"Bullets to rewrite:\n{json.dumps(bullets)}",
            max_tokens=1500,
            quality=True,
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return bullets
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return bullets

    async def infer_salary(self, experience_years: int, location: str, company: str) -> str:
        raw = await self._call_haiku(
            f"Give a realistic salary range for a software engineer with {experience_years} years experience "
            f"at {company} in {location}. "
            f"Return ONLY the range in this exact format: '$X,000 - $Y,000' or 'KES X,000 - KES Y,000' "
            f"based on the location. No other text.",
            max_tokens=30,
        )
        # If Haiku still returns prose, extract just the range pattern
        import re
        match = re.search(r'[\$€£KES][\d,\s]+[-–][\s]*[\$€£KES]?[\d,\s]+', raw)
        return match.group(0).strip() if match else "$80,000 - $120,000"

    async def generate_summary(
        self,
        profile,
        keywords: list[str],
        role: str,
        immutable_facts: str = "",
        experience: list[dict] | None = None,
        jd: str = "",
        positioning_brief: str = "",
    ) -> str:
        exp = experience if experience is not None else (profile.work_experience or [])
        years = getattr(profile, "years_of_experience", None)
        years_phrase = f"{years} years of" if years else f"{len(exp)} roles of" if exp else "relevant"

        context_block = ""
        if positioning_brief:
            context_block += f"POSITIONING CONTEXT (use this to frame the summary):\n{positioning_brief}\n\n"
        if jd:
            context_block += f"JOB DESCRIPTION (first 2500 chars):\n{jd[:2500]}\n\n"

        return await self._call_haiku(
            f"Write a punchy 2-sentence professional summary for a {role} application.\n"
            f"Sentence 1: a sharp value proposition — who this person is and what they bring to this role.\n"
            f"Sentence 2: the 1-2 most relevant strengths that make them a top contender for THIS specific role.\n\n"
            f"{context_block}"
            f"{immutable_facts}\n\n"
            f"Rules:\n"
            f"- Be specific to THIS role — no generic filler phrases\n"
            f"- Include quantified achievements only if they appear in the profile data\n"
            f"- Do NOT invent or fabricate any achievements, metrics, or time periods\n"
            f"- Naturally include these JD keywords: {', '.join(keywords[:12])}\n"
            f"- Make every word earn its place — HMs spend 7 seconds on a resume\n"
            f"- Return plain text only, no markdown, no headers",
            max_tokens=200,
            quality=True,
        )

    def _extract_bullets(self, experience: list[dict]) -> list[tuple[int, str]]:
        """Extract bullets from experience, returning (job_index, bullet) pairs.
        Handles both list and newline-separated string formats."""
        pairs = []
        for i, job in enumerate(experience):
            resp = job.get("responsibilities", [])
            if isinstance(resp, str):
                bullets = [b.strip() for b in resp.split("\n") if b.strip()]
            elif isinstance(resp, list):
                bullets = [str(b).strip() for b in resp if str(b).strip()]
            else:
                bullets = []
            for b in bullets:
                pairs.append((i, b))
        return pairs

    def _build_html(
        self,
        profile: CampaignProfile,
        experience: list[dict],
        rewritten_by_job: dict[int, list[str]],
        keywords: list[str],
        top_competencies: list[str],
        summary: str,
        salary: str,
        resume_skills: list[str] | None = None,
        positioning_skills: list[str] | None = None,
        target_role: str = "",
        projects: list[dict] | None = None,
    ) -> str:
        """Build the full resume HTML matching the exact design template."""

        def esc(s: str) -> str:
            return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # --- Experience HTML ---
        exp_html = ""
        for i, job in enumerate(experience):
            bullets = rewritten_by_job.get(i, [])
            bullets_html = "".join(f"<li>{esc(b)}</li>" for b in bullets if b.strip())
            company_name = esc(job.get("company", ""))
            location = esc(job.get("location", ""))
            company_url = job.get("company_url", "")
            linkedin_url = job.get("linkedin_url", "")
            start_d = (job.get("start_date") or "").strip()
            end_d = (job.get("end_date") or "").strip()
            if start_d:
                dates_html = f'<span class="job-dates">{esc(start_d)} &ndash; {esc(end_d) if end_d else "Present"}</span>'
            else:
                dates_html = '<span class="job-dates-missing">&#9888; Add dates</span>'

            company_links = ""
            if company_url:
                company_links += f' | <a href="{esc(company_url)}">{esc(company_url.replace("https://","").replace("http://",""))}</a>'
            if linkedin_url:
                company_links += f' | <a href="{esc(linkedin_url)}">LinkedIn</a>'

            dates_suffix = f' &nbsp;|&nbsp; {dates_html}' if dates_html else ''
            exp_html += f"""
        <div class="job">
            <div class="job-header">
                <span class="job-title">{esc(job.get('title', ''))}</span>
            </div>
            <div class="job-company">{company_name}{f" &mdash; {location}" if location else ""}{company_links}{dates_suffix}</div>
            <ul class="achievements">{bullets_html}</ul>
        </div>"""

        # --- Skills grid ---
        # If positioning_skills were generated by the brief, use those (role-language aware).
        # Otherwise fall back to JD-matched profile skills.
        display_skills = (positioning_skills or resume_skills or (profile.skills or []))[:12]

        skill_cats = {
            "Languages": ["Python", "JavaScript", "TypeScript", "Java", "Go", "Kotlin", "Swift", "Dart", "SQL", "C++", "Rust", "Ruby", "PHP"],
            "Frontend": ["React", "Next.js", "Vue.js", "Angular", "Svelte", "Tailwind", "Redux", "HTML", "CSS"],
            "Backend": ["Node.js", "Express", "FastAPI", "Django", "Flask", "Spring", "GraphQL", "REST", "gRPC"],
            "Databases": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Neo4j", "Cassandra", "DynamoDB"],
            "AI/ML": ["TensorFlow", "PyTorch", "LangChain", "RAG", "BERT", "Transformers", "Claude", "OpenAI", "Hugging Face"],
            "Cloud & DevOps": ["AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD", "GitHub Actions", "Jenkins"],
            "Mobile": ["React Native", "Flutter", "SwiftUI", "Jetpack", "Firebase", "CoreData"],
            "Tools": ["Git", "Kafka", "Airflow", "Prometheus", "Grafana", "Agile", "Scrum", "TDD"],
        }
        skills_html = ""
        categorised: set[str] = set()
        for cat, markers in skill_cats.items():
            matched = [s for s in display_skills if any(m.lower() in s.lower() for m in markers)]
            if matched:
                categorised.update(matched)
                skills_html += f"""
            <div class="skill-category">
                <span class="skill-label">{cat}: </span>
                <span class="skill-items">{esc(", ".join(matched))}</span>
            </div>"""
        # Catch-all: anything not matched by a tech category renders as "Core Skills"
        uncategorised = [s for s in display_skills if s not in categorised]
        if uncategorised:
            skills_html += f"""
            <div class="skill-category">
                <span class="skill-label">Core Skills: </span>
                <span class="skill-items">{esc(", ".join(uncategorised))}</span>
            </div>"""

        # --- Education ---
        edu_html = ""
        certs_html = ""
        for edu in (profile.education or []):
            degree = esc(edu.get("degree", ""))
            field = esc(edu.get("field_of_study", ""))
            inst = esc(edu.get("institution", ""))
            year = esc(str(edu.get("graduation_year", "")))
            inst_url = edu.get("institution_url", "")
            inst_display = f'<a href="{esc(inst_url)}">{inst}</a>' if inst_url else inst
            cert = edu.get("is_certification", False)
            if cert:
                certs_html += f'<span class="cert-item">{degree}{f" ({field})" if field else ""}</span>'
            else:
                edu_html += f'<div class="edu-item"><strong>{degree}{f" in {field}" if field else ""}</strong> &mdash; {inst_display}</div>'

        # --- Projects --- (max 2 to stay on page 1)
        proj_html = ""
        for proj in (projects or profile.projects or [])[:2]:
            name = esc(proj.get("name", ""))
            # Truncate at sentence boundary within 220 chars
            raw_desc = (proj.get("description", "") or "")
            if len(raw_desc) > 220:
                cut = raw_desc[:220].rfind(". ")
                raw_desc = raw_desc[:cut + 1] if cut > 80 else raw_desc[:220].rstrip() + "…"
            desc = esc(raw_desc)
            tech = proj.get("tech_stack", [])
            if isinstance(tech, list):
                tech_str = esc(", ".join(tech[:5]))  # cap at 5 items
            else:
                tech_str = esc(str(tech))
            link = proj.get("link", "")
            title_html = f'<a href="{esc(link)}">{name}</a>' if link else name
            proj_html += f"""
            <div class="project">
                <div class="project-title">{title_html}</div>
                <div class="project-desc">{desc}{f'<span class="tech"> &mdash; {tech_str}</span>' if tech_str else ''}</div>
            </div>"""

        # --- Contact links ---
        email = esc(profile.email or "")
        phone = esc(profile.phone or "")
        city = esc(profile.city or "")
        country = esc(profile.country or "")
        linkedin = profile.linkedin_url or ""
        github = profile.github_url or ""
        portfolio = profile.portfolio_url or ""

        contact_parts = []
        if email:
            contact_parts.append(f'<a href="mailto:{email}">{email}</a>')
        if phone:
            contact_parts.append(phone)
        if city or country:
            contact_parts.append(f"{city}{', ' + country if country else ''}")
        if linkedin:
            slug = linkedin.rstrip("/").split("/")[-1]
            contact_parts.append(f'<a href="{esc(linkedin)}">linkedin.com/in/{esc(slug)}</a>')
        if github:
            slug = github.rstrip("/").split("/")[-1]
            contact_parts.append(f'<a href="{esc(github)}">github.com/{esc(slug)}</a>')
        if portfolio:
            display = portfolio.replace("https://", "").replace("http://", "").rstrip("/")
            contact_parts.append(f'<a href="{esc(portfolio)}">{esc(display)}</a>')

        contact_html = ' <span class="divider">|</span> '.join(contact_parts)

        competencies_str = esc(", ".join(top_competencies))
        name_str = esc((profile.full_name or "").upper())

        # Tagline: role title split into ~3 keyword phrases joined with bullet
        # e.g. "Backend / API Engineer, Billing" → "Backend Engineer • API Engineer • Billing"
        import re as _re
        # Tagline: target role first, then 2 top competencies (short names only)
        tagline_parts = []
        role_label = target_role or (experience[0].get("title", "") if experience else "")
        if role_label:
            tagline_parts.append(esc(role_label))
        for t in top_competencies:
            if len(tagline_parts) >= 3:
                break
            # Skip anything that looks like a verbose description (contains parens or is too long)
            if "(" not in t and len(t) <= 35:
                tagline_parts.append(esc(t))
        if not tagline_parts:
            tagline_parts = [esc(p.strip()) for p in _re.split(r'[,/|&]', role_label) if p.strip()][:3]
        tagline_html = " &bull; ".join(tagline_parts)

        # Pre-compute to avoid backslash-in-f-string (SyntaxError on Python < 3.12)
        certs_block = ('<div class="certs-list">' + certs_html + '</div>') if certs_html.strip() else ''
        edu_section = (
            '<section class="section"><h2 class="section-title">Education &amp; Credentials</h2>'
            '<div class="edu-grid">' + edu_html + '</div>' + certs_block + '</section>'
        ) if (edu_html.strip() or certs_html.strip()) else ''

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
:root {{ --primary:#1a1a2e; --accent:#16213e; --text:#2d2d2d; --text-light:#555; --border:#e0e0e0; }}
@page {{ size:A4; margin:10mm 12mm; }}
body {{
    font-family:'Source Sans 3',sans-serif; font-size:9pt; line-height:1.4;
    color:var(--text); background:#fff; max-width:210mm; margin:0 auto; padding:8mm 10mm;
}}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.header {{ text-align:center; padding-bottom:8px; border-bottom:2px solid var(--primary); margin-bottom:10px; }}
.name {{ font-family:'Cormorant Garamond',serif; font-size:26pt; font-weight:600; color:var(--primary); letter-spacing:2px; margin-bottom:3px; }}
.tagline {{ font-size:9pt; color:var(--text-light); margin-bottom:5px; font-weight:500; }}
.contact-row {{ display:flex; justify-content:center; flex-wrap:wrap; gap:3px 14px; font-size:8.5pt; color:var(--text-light); }}
.contact-row a {{ color:var(--text-light); }}
.divider {{ color:var(--border); }}
.section {{ margin-bottom:8px; }}
.section-title {{
    font-family:'Cormorant Garamond',serif; font-size:11pt; font-weight:600;
    color:var(--primary); text-transform:uppercase; letter-spacing:1.5px;
    border-bottom:1px solid var(--border); padding-bottom:2px; margin-bottom:6px;
}}
.summary {{ font-size:9pt; line-height:1.45; text-align:justify; }}
.keywords {{ font-size:8.5pt; color:var(--text-light); margin-top:5px; line-height:1.35; }}
.keywords strong {{ color:var(--primary); }}
.job {{ margin-bottom:8px; }}
.job:last-child {{ margin-bottom:0; }}
.job-header {{ margin-bottom:1px; }}
.job-title {{ font-weight:600; font-size:9.5pt; color:var(--primary); }}
.job-dates {{ font-size:8.5pt; color:var(--text-light); font-weight:400; }}
.job-dates-missing {{ font-size:7.5pt; color:#b91c1c; font-weight:600; }}
.job-company {{ font-size:8.5pt; color:var(--text-light); margin-bottom:4px; }}
.job-company a {{ color:var(--accent); }}
.achievements {{ list-style:none; padding-left:0; }}
.achievements li {{
    position:relative; padding-left:10px; margin-bottom:2px; font-size:8.5pt; line-height:1.35;
}}
.achievements li::before {{ content:"›"; position:absolute; left:0; color:var(--accent); font-size:9pt; }}
.skills-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:3px 18px; }}
.skill-category {{ margin-bottom:2px; }}
.skill-label {{ font-weight:600; font-size:8.5pt; color:var(--primary); }}
.skill-items {{ font-size:8pt; color:var(--text-light); }}
.edu-grid {{ display:flex; flex-wrap:wrap; gap:3px 18px; }}
.edu-item {{ font-size:8.5pt; }}
.edu-item strong {{ color:var(--primary); }}
.certs-list {{
    display:flex; flex-wrap:wrap; gap:2px 12px; font-size:8pt;
    color:var(--text-light); margin-top:5px; padding-top:5px; border-top:1px dashed var(--border);
}}
.cert-item::before {{ content:"\u2713 "; color:var(--accent); }}
.project {{ margin-bottom:5px; }}
.project-title {{ font-weight:600; font-size:9pt; color:var(--primary); margin-bottom:1px; }}
.project-title a {{ color:var(--primary); }}
.project-desc {{
    font-size:8pt; color:var(--text-light); line-height:1.35;
    position:relative; padding-left:10px;
}}
.project-desc::before {{ content:"›"; position:absolute; left:0; color:var(--accent); font-size:7pt; }}
.tech {{ font-style:italic; }}
.achievement-item {{
    font-size:8pt; line-height:1.35; margin-bottom:2px;
    position:relative; padding-left:10px;
}}
.achievement-item::before {{ content:"›"; position:absolute; left:0; color:var(--accent); font-size:7pt; }}
@media print {{
    body {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; padding:0; }}
    a {{ color:var(--accent) !important; }}
}}
</style>
</head>
<body>
<header class="header">
    <h1 class="name">{name_str}</h1>
    <p class="tagline">{tagline_html}</p>
    <div class="contact-row">{contact_html}</div>
</header>

<section class="section">
    <h2 class="section-title">Professional Summary</h2>
    <p class="summary">{esc(summary)}</p>
    <p class="keywords"><strong>Core Competencies:</strong> {competencies_str}</p>
</section>

{f'<section class="section"><h2 class="section-title">Professional Experience</h2>{exp_html}</section>' if exp_html.strip() else ''}

{f'<section class="section"><h2 class="section-title">Skills</h2><div class="skills-grid">{skills_html}</div></section>' if skills_html.strip() else ''}

{edu_section}

{f'<section class="section"><h2 class="section-title">Key Projects</h2>{proj_html}</section>' if proj_html else ''}

{('<section class="section"><h2 class="section-title">Impact &amp; Achievements</h2>' + "".join(f'<div class="achievement-item">{esc(a)}</div>' for a in (getattr(profile, "achievements", None) or []) if a) + '</section>') if (getattr(profile, "achievements", None) or []) else ''}

</body>
</html>"""

    def _generate_pdf_sync(self, html: str, output_path: Path) -> None:
        """
        Generate PDF using Chrome's --print-to-pdf CLI flag via subprocess.Popen.
        This is fully synchronous — no asyncio, no event loop — so it works on
        both SelectorEventLoop and ProactorEventLoop on Windows.
        """
        import os
        import subprocess
        import tempfile

        # Locate Chrome (try common Windows paths, then fall back to PATH)
        chrome_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\Admin\AppData\Local\Google\Chrome\Application\chrome.exe",
        ]
        chrome_exe = next((p for p in chrome_candidates if os.path.isfile(p)), "chrome")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            tmp_html = f.name

        try:
            subprocess.run(
                [
                    chrome_exe,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--run-all-compositor-stages-before-draw",
                    f"--print-to-pdf={str(output_path)}",
                    "--print-to-pdf-no-header",
                    "--no-pdf-header-footer",
                    f"file:///{tmp_html.replace(chr(92), '/')}",
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        finally:
            os.unlink(tmp_html)

    async def _build_positioning_brief(
        self,
        profile,
        experience: list[dict],
        jd: str,
        target_role: str,
        target_company: str,
    ) -> dict:
        """
        Produce a cross-domain positioning brief before writing any resume content.

        Returns: { "narrative": str, "skills": list[str] }

        The narrative is 2-3 sentences that explain WHY this person is credible for
        this specific role — even if their background doesn't match on the surface.
        The skills list contains 10-15 role-relevant skills honestly derivable from
        the profile, phrased in the target domain's language.
        """
        exp_titles = "; ".join(
            f"{j.get('title', '')} at {j.get('company', '')}" for j in experience[:5] if j.get("title")
        )
        raw_ctx = (getattr(profile, "raw_context", None) or "")[:3000]
        profile_skills = ", ".join((profile.skills or [])[:20])
        years = getattr(profile, "years_of_experience", None) or len(experience)

        raw = await self._call_haiku(
            f"You are a senior career strategist. Your job is to position a candidate as a top contender "
            f"for a role, using ONLY what is genuinely true about them.\n\n"
            f"TARGET ROLE: {target_role} at {target_company}\n\n"
            f"CANDIDATE PROFILE:\n"
            f"  Years of experience: {years}\n"
            f"  Experience titles: {exp_titles or 'See raw context'}\n"
            f"  Skills on profile: {profile_skills}\n"
            f"  Raw context (CV/profile text):\n{raw_ctx}\n\n"
            f"JOB DESCRIPTION:\n{jd[:3000]}\n\n"
            f"TASK: Return a JSON object with two keys:\n"
            f'  "narrative": 2-3 sentences. Identify the GENUINE credibility bridges between this '
            f"person's background and this role. Be specific — name actual domain knowledge, tools, "
            f"or experiences that transfer. Don't say 'passion for' or 'quick learner'. "
            f"Find real hooks: deep technical knowledge of a domain they want to write about, "
            f"measurable impact, leadership, or niche expertise the competition won't have.\n"
            f'  "skills": array of 10-15 SHORT skill names. '
            f"Each must be 1-4 words maximum — e.g. 'Ruby on Rails', 'PostgreSQL', 'M-Pesa API', "
            f"'Agile/Scrum', 'React.js', 'AWS', 'Technical Leadership'. "
            f"NO verbose descriptions, NO parenthetical expansions, NO sentences. "
            f"Derive them honestly from the profile, named in the target industry's vocabulary.\n\n"
            f"Rules:\n"
            f"- NEVER invent experience, companies, degrees, or metrics not in the profile\n"
            f"- Do translate domain language naturally (e.g. 'built payment APIs' → 'deep expertise "
            f"in stablecoin/fintech infrastructure' for a crypto content role)\n"
            f"- Return ONLY valid JSON, no explanation",
            max_tokens=600,
            quality=True,
        )
        # Parse JSON
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {"narrative": "", "skills": []}
        try:
            result = json.loads(raw[start:end])
            return {
                "narrative": str(result.get("narrative", "")),
                "skills": list(result.get("skills", [])),
            }
        except (json.JSONDecodeError, ValueError):
            return {"narrative": "", "skills": []}

    async def _extract_projects_from_raw_context(self, raw_context: str) -> list[dict]:
        """
        Parse raw profile text into structured project entries.
        Called when profile.projects is empty but raw_context exists.
        """
        if not raw_context or not raw_context.strip():
            return []
        raw = await self._call_haiku(
            f"Extract personal/side projects from this candidate profile text. "
            f"Return a JSON array where each item has: "
            f'name (string), description (string — 1-2 sentences, concrete and specific), '
            f'tech_stack (array of strings), link (string or null). '
            f"Include ALL projects mentioned. "
            f"Return ONLY valid JSON, no explanation.\n\n"
            f"Profile text:\n{raw_context[:5000]}",
            max_tokens=1000,
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            result = json.loads(raw[start:end])
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    async def rewrite_project_descriptions(
        self,
        projects: list[dict],
        keywords: list[str],
        target_role: str,
        target_company: str,
        jd: str,
    ) -> list[dict]:
        """
        Rewrite each project description to highlight the angle most relevant to the JD.

        Developer-Core applied to a fintech role → lead with the payment integrations,
        financial workflows, and scale. Don't mention the interview simulator.
        Same project applied to an AI role → lead with Claude API, emotion detection, ML pipeline.

        Rules: never invent features that don't exist. Only re-angle what's actually there.
        """
        if not projects:
            return projects

        projects_json = json.dumps([
            {"name": p.get("name", ""), "description": p.get("description", ""), "tech_stack": p.get("tech_stack", [])}
            for p in projects
        ])

        raw = await self._call_haiku(
            f"You are rewriting project descriptions on a resume for a specific job application.\n\n"
            f"TARGET ROLE: {target_role} at {target_company}\n"
            f"JD CONTEXT: {jd[:1500]}\n\n"
            f"PROJECTS:\n{projects_json}\n\n"
            f"TASK: For each project, rewrite the description (1-2 sentences max) to highlight "
            f"the aspects most relevant to the target role. "
            f"Focus on the angle the hiring manager cares about — if it's fintech, lead with "
            f"payments/financial flows/scale. If it's AI, lead with ML/models/pipelines. "
            f"If it's PM, lead with delivery/coordination/stakeholders.\n\n"
            f"RULES:\n"
            f"- NEVER invent features or integrations not present in the original description\n"
            f"- Keep it to 1-2 tight sentences — no padding\n"
            f"- Weave in these JD keywords naturally where they genuinely fit: {', '.join(keywords[:10])}\n"
            f"- Return a JSON array with same length as input, each item has 'name' and 'description' only\n"
            f"- No explanation, valid JSON only",
            max_tokens=600,
            quality=True,
        )

        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return projects
        try:
            rewritten = json.loads(raw[start:end])
            result = []
            for i, proj in enumerate(projects):
                updated = dict(proj)
                if i < len(rewritten) and rewritten[i].get("description"):
                    updated["description"] = rewritten[i]["description"]
                result.append(updated)
            return result
        except (json.JSONDecodeError, ValueError):
            return projects

    def _pick_relevant_projects(self, projects: list[dict], jd: str, top_n: int = 3) -> list[dict]:
        """Pick the most JD-relevant projects using sentence-transformers."""
        if not projects:
            return []
        descriptions = [
            f"{p.get('name', '')} {p.get('description', '')} {' '.join(p.get('tech_stack', []))}"
            for p in projects
        ]
        ranked = matcher.match_skills(jd, descriptions, top_n=top_n)
        # match_skills returns strings — map back to project dicts by index
        picked = []
        for desc in ranked:
            for i, d in enumerate(descriptions):
                if d == desc and projects[i] not in picked:
                    picked.append(projects[i])
                    break
        # If matcher failed, fall back to first top_n
        return picked if picked else projects[:top_n]

    async def _extract_experience_from_raw_context(self, raw_context: str) -> list[dict]:
        """
        Parse raw profile text into structured work experience entries.
        Called when profile.work_experience is empty but raw_context exists.
        """
        if not raw_context or not raw_context.strip():
            return []
        raw = await self._call_haiku(
            f"Extract work experience from this candidate profile text. "
            f"Return a JSON array where each item has: "
            f'title (string), company (string), location (string), '
            f'start_date (string, e.g. "Jan 2020"), end_date (string or "Present"), '
            f'responsibilities (array of bullet strings). '
            f"Return ONLY valid JSON, no explanation.\n\n"
            f"Profile text:\n{raw_context[:4000]}",
            max_tokens=2000,
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            result = json.loads(raw[start:end])
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    async def tailor_for_listing(self, listing_id: str, user_id: str) -> Application | None:
        # Idempotency check — only skip if already tailored
        existing_result = await self.db.execute(
            select(Application).where(
                Application.job_listing_id == listing_id,
                Application.user_id == user_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing and existing.tailored_resume_pdf_url:
            return existing

        listing_result = await self.db.execute(select(JobListing).where(JobListing.id == listing_id))
        listing = listing_result.scalar_one_or_none()
        if not listing or not listing.description:
            return None

        profile_result = await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == listing.campaign_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return None

        company = (listing.company or "")[:100]
        title = (listing.title or "")[:150]
        location = (listing.location or "remote")[:100]

        # Use structured work_experience if available; fall back to parsing raw_context
        experience = profile.work_experience or []
        if not experience and profile.raw_context:
            experience = await self._extract_experience_from_raw_context(profile.raw_context)

        # ── Build immutable facts block (injected into every LLM prompt) ──────
        immutable_facts = _build_immutable_facts(profile, experience)

        # --- Pre-filter: skip tailoring for very poor fits ---
        profile_text = (
            f"{', '.join((profile.skills or [])[:20])} | "
            f"{' | '.join(j.get('title', '') or '' for j in experience[:3])} | "
            f"{profile.years_of_experience or len(experience)} years experience"
        )
        fit_score = matcher.score_fit(listing.description, profile_text)
        import logging as _logging
        _logging.getLogger(__name__).info(
            "tailor_for_listing: fit_score=%.3f for %s @ %s", fit_score, title, company
        )

        # --- Parallel: extract keywords (LLM) + local skill matching ---
        bullet_pairs = self._extract_bullets(experience)
        bullets_only = [b for _, b in bullet_pairs]

        jd_full = (listing.description or "")

        # Extract projects from raw_context if profile.projects is empty
        profile_projects = profile.projects or []
        if not profile_projects and profile.raw_context:
            profile_projects = await self._extract_projects_from_raw_context(profile.raw_context)

        relevant_projects = self._pick_relevant_projects(profile_projects, jd_full, top_n=2)

        # ── Single LLM call — replaces all individual keyword/summary/bullet/project calls ──
        result = await self._tailor_all(
            profile=profile,
            experience=experience,
            projects=relevant_projects,
            jd=jd_full,
            target_role=title,
            target_company=company,
            immutable_facts=immutable_facts,
            bullets=bullets_only,
        )

        keywords: list[str]          = result.get("keywords") or []
        positioning_narrative: str   = result.get("positioning_narrative") or ""
        positioning_skills: list[str] = result.get("positioning_skills") or []
        summary: str                 = result.get("summary") or ""
        rewritten: list[str]         = result.get("rewritten_bullets") or bullets_only
        rewritten_projects_raw       = result.get("rewritten_projects") or []

        # Merge rewritten descriptions back into project dicts
        relevant_projects = [
            {**proj, "description": rewritten_projects_raw[i]["description"]}
            if i < len(rewritten_projects_raw) and rewritten_projects_raw[i].get("description")
            else proj
            for i, proj in enumerate(relevant_projects)
        ]

        # top_competencies: use positioning skills (role-language aware) or fall back to local matcher
        if positioning_skills:
            top_competencies = positioning_skills[:8]
        else:
            top_competencies = self.pick_top_competencies(jd_full, profile.skills or [])

        resume_skills = self.pick_resume_skills(jd_full, profile.skills or [])

        # Salary — small fast Flash call, runs after the big call
        salary = await self.infer_salary(profile.years_of_experience or len(experience), location, company)

        # --- Map rewritten bullets back to jobs ---
        rewritten_by_job: dict[int, list[str]] = {}
        for idx, (job_idx, _) in enumerate(bullet_pairs[:20]):
            rewritten_by_job.setdefault(job_idx, []).append(
                rewritten[idx] if idx < len(rewritten) else bullets_only[idx]
            )

        html = self._build_html(
            profile=profile,
            experience=experience,
            rewritten_by_job=rewritten_by_job,
            keywords=keywords,
            top_competencies=top_competencies,
            summary=summary,
            salary=salary,
            resume_skills=resume_skills,
            positioning_skills=positioning_skills,
            target_role=title,
            projects=relevant_projects,
        )

        import re
        def slugify(s: str) -> str:
            s = s.strip().lower()
            s = re.sub(r'[^a-z0-9]+', '_', s)
            return s.strip('_')[:40]

        # Fetch campaign name for the folder hierarchy
        from app.models.pg.job_hunter import JobHunterCampaign
        campaign_result = await self.db.execute(
            select(JobHunterCampaign).where(JobHunterCampaign.id == listing.campaign_id)
        )
        campaign_obj = campaign_result.scalar_one_or_none()
        campaign_name = (campaign_obj.name if campaign_obj else listing.campaign_id)

        # Sanitise display chars that are invalid on Windows/macOS filenames
        def safe(s: str, maxlen: int = 50) -> str:
            return re.sub(r'[\\/:*?"<>|]', '', s)[:maxlen].strip()

        candidate_display = (profile.full_name or "Candidate").strip()
        company_display = company.strip()
        role_display = title.strip()

        # Folder per job: resumes/{campaign_name}/{company}/{role}/
        job_folder = (
            RESUMES_BASE
            / slugify(campaign_name)
            / slugify(company)
            / slugify(title)
        )
        job_folder.mkdir(parents=True, exist_ok=True)

        # Filename: "Full Name - Company - Role.pdf"
        pdf_filename = f"{safe(candidate_display)} - {safe(company_display)} - {safe(role_display)}.pdf"
        pdf_path = job_folder / pdf_filename
        await asyncio.to_thread(self._generate_pdf_sync, html, pdf_path)

        form_answers = {
            "salary": salary,
            "summary": summary,
            "rewritten_bullets": rewritten,
            "top_competencies": top_competencies,
        }

        if existing:
            # Update the pre-created pending record
            existing.tailored_resume_pdf_url = str(pdf_path)
            existing.form_answers = form_answers
            existing.status = "tailored"
            application = existing
        else:
            application = Application(
                id=str(uuid.uuid4()),
                campaign_id=listing.campaign_id,
                job_listing_id=listing.id,
                user_id=user_id,
                tailored_resume_pdf_url=str(pdf_path),
                form_answers=form_answers,
                status="tailored",
            )
            self.db.add(application)

        listing.status = "applying"
        try:
            await self.db.commit()
        except Exception as exc:
            # Race condition: ensure_application already created the record between our
            # initial SELECT and this commit — re-fetch and update instead of insert.
            if "UniqueViolationError" in str(exc) or "uq_applications_listing_user" in str(exc):
                await self.db.rollback()
                race_result = await self.db.execute(
                    select(Application).where(
                        Application.job_listing_id == listing_id,
                        Application.user_id == user_id,
                    )
                )
                application = race_result.scalar_one()
                application.tailored_resume_pdf_url = str(pdf_path)
                application.cover_letter = cover_letter
                application.form_answers = form_answers
                application.status = "tailored"
                listing.status = "applying"
                await self.db.commit()
            else:
                raise
        return application
