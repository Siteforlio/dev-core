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

RESUMES_DIR = Path(__file__).parent.parent.parent.parent / "resumes"
RESUMES_DIR.mkdir(exist_ok=True)

# Semaphore is created lazily per event loop to avoid "bound to a different event loop"
# errors when Celery re-uses the same process across multiple asyncio.run() calls.
_HAIKU_SEM: asyncio.Semaphore | None = None


def _get_haiku_sem() -> asyncio.Semaphore:
    global _HAIKU_SEM
    loop = asyncio.get_event_loop()
    if _HAIKU_SEM is None or _HAIKU_SEM._loop is not loop:
        _HAIKU_SEM = asyncio.Semaphore(4)
    return _HAIKU_SEM


class TailorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _call_haiku(self, prompt: str, max_tokens: int = 1000) -> str:
        async with _get_haiku_sem():
            return await call_llm(prompt, max_tokens)

    async def extract_keywords(self, jd: str) -> list[str]:
        raw = await self._call_haiku(
            f"Extract the 15 most important ATS keywords from this job description. "
            f"Return a JSON array of strings only, no explanation.\n\n{jd[:3000]}"
        )
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            return []

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
            domain_context += f"\nROLE CONTEXT: {jd_summary[:300]}"

        raw = await self._call_haiku(
            f"You are rewriting resume bullets so a candidate looks like a strong fit for a new role.\n\n"
            f"{domain_context}\n\n"
            f"TASK: For each bullet, keep the achievement (the numbers, the scale, the outcome) "
            f"but translate the CONTEXT into the language of the target role. "
            f"The achievement belongs to the candidate — just tell it in the vocabulary of the new field.\n\n"
            f"DOMAIN TRANSLATION EXAMPLES:\n"
            f'  Doctor → Software Engineer: "Managed care plans for 200 patients, reducing readmissions by 30%"'
            f' → "Managed lifecycle for 200+ service accounts, reducing churn by 30%"\n'
            f'  Teacher → Data Analyst: "Tracked progress of 35 students, improving pass rates by 20%"'
            f' → "Tracked performance metrics for 35 data pipelines, improving accuracy by 20%"\n\n'
            f"RULES:\n"
            f"- NEVER change the numbers or scale (if original says 200, keep 200)\n"
            f"- NEVER invent achievements that don't exist in the original\n"
            f"- DO translate domain language to fit the target role\n"
            f"- Use strong ownership verbs: Architected, Engineered, Led, Built, Designed, Reduced, Increased\n"
            f"- Naturally weave in these JD keywords where they fit: {', '.join(keywords[:10])}\n"
            f"- Every bullet MUST end with a measurable outcome (%, count, time saved, cost reduced)\n"
            f"- Return a JSON array of rewritten bullet strings only, no explanation\n\n"
            f"Bullets to rewrite:\n{json.dumps(bullets)}",
            max_tokens=1500,
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

    async def generate_summary(self, profile: CampaignProfile, keywords: list[str], role: str) -> str:
        exp = profile.work_experience or []
        years = getattr(profile, "years_of_experience", None)
        years_phrase = f"{years} years of" if years else f"{len(exp)} roles of"
        return await self._call_haiku(
            f"Write a 2-3 sentence professional summary for a {role} application.\n"
            f"Candidate has {years_phrase} experience. "
            f"Top skills: {', '.join((profile.skills or [])[:12])}.\n"
            f"Rules:\n"
            f"- Use exactly '{years_phrase}' — do NOT change, round up, or invent a different number\n"
            f"- Include quantified achievements only if they appear in the profile data below\n"
            f"- Do NOT invent or fabricate any achievements, metrics, or time periods\n"
            f"- Naturally include these JD keywords: {', '.join(keywords[:6])}\n"
            f"- Return plain text only, no markdown, no headers",
            max_tokens=200,
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

            exp_html += f"""
        <div class="job">
            <div class="job-header">
                <span class="job-title">{esc(job.get('title', ''))}</span>
                {dates_html}
            </div>
            <div class="job-company">{company_name}{f" &mdash; {location}" if location else ""}{company_links}</div>
            <ul class="achievements">{bullets_html}</ul>
        </div>"""

        # --- Skills grid ---
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
        # Use only the JD-relevant skills selected by pick_resume_skills (max 20)
        display_skills = resume_skills or (profile.skills or [])[:20]
        skills_html = ""
        for cat, markers in skill_cats.items():
            matched = [s for s in display_skills if any(m.lower() in s.lower() for m in markers)]
            if matched:
                skills_html += f"""
            <div class="skill-category">
                <span class="skill-label">{cat}: </span>
                <span class="skill-items">{esc(", ".join(matched))}</span>
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

        # --- Projects ---
        proj_html = ""
        for proj in (profile.projects or [])[:4]:
            name = esc(proj.get("name", ""))
            desc = esc((proj.get("description", ""))[:200])
            tech = proj.get("tech_stack", [])
            if isinstance(tech, list):
                tech_str = esc(", ".join(tech))
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
        raw_title = (experience[0].get("title", "") if experience else "") or ""
        # Use top_competencies + role for tagline keywords (3 items)
        tagline_parts = [esc(t) for t in top_competencies[:3]] if top_competencies else []
        if not tagline_parts:
            tagline_parts = [esc(p.strip()) for p in _re.split(r'[,/|&]', raw_title) if p.strip()][:3]
        tagline_html = " &bull; ".join(tagline_parts)

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
.job-header {{ display:flex; justify-content:space-between; align-items:baseline; }}
.job-title {{ font-weight:600; font-size:9.5pt; color:var(--primary); }}
.job-dates {{ font-size:8.5pt; color:var(--text-light); }}
.job-dates-missing {{ font-size:7.5pt; color:#b91c1c; font-weight:600; }}
.job-company {{ font-size:8.5pt; color:var(--text-light); margin-bottom:4px; }}
.job-company a {{ color:var(--accent); }}
.achievements {{ list-style:none; padding-left:0; }}
.achievements li {{
    display:flex; gap:5px; margin-bottom:2px; font-size:8.5pt; line-height:1.35;
}}
.achievements li::before {{ content:"\u2022"; color:var(--accent); font-size:9pt; flex-shrink:0; margin-top:0; }}
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
    display:flex; gap:5px; font-size:8pt; color:var(--text-light); line-height:1.35;
}}
.project-desc::before {{ content:"\u2022"; color:var(--accent); flex-shrink:0; }}
.tech {{ font-style:italic; }}
.achievement-item {{
    display:flex; gap:5px; font-size:8pt; line-height:1.35; margin-bottom:3px;
}}
.achievement-item::before {{ content:"\u2022"; color:var(--accent); flex-shrink:0; }}
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

<section class="section">
    <h2 class="section-title">Professional Experience</h2>
    {exp_html}
</section>

<section class="section">
    <h2 class="section-title">Technical Skills</h2>
    <div class="skills-grid">{skills_html}</div>
</section>

<section class="section">
    <h2 class="section-title">Education &amp; Credentials</h2>
    <div class="edu-grid">{edu_html}</div>
    {f'<div class="certs-list">{certs_html}</div>' if certs_html else ''}
</section>

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
                    f"file:///{tmp_html.replace(chr(92), '/')}",
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        finally:
            os.unlink(tmp_html)

    async def tailor_for_listing(self, listing_id: str, user_id: str) -> Application | None:
        # Idempotency check
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

        profile_result = await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == listing.campaign_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return None

        company = (listing.company or "")[:100]
        title = (listing.title or "")[:150]
        location = (listing.location or "remote")[:100]
        experience = profile.work_experience or []

        # --- Pre-filter: skip tailoring for very poor fits ---
        profile_text = (
            f"{', '.join((profile.skills or [])[:20])} | "
            f"{' | '.join(j.get('title', '') for j in experience[:3])} | "
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

        keywords, = await asyncio.gather(self.extract_keywords(listing.description))

        # Skill matching is now local (sentence-transformers) — no LLM calls
        top_competencies = self.pick_top_competencies(listing.description, profile.skills or [])
        resume_skills = self.pick_resume_skills(listing.description, profile.skills or [])

        # JD summary for domain translation context (first 400 chars of description)
        jd_summary = (listing.description or "")[:400]

        summary, salary, rewritten = await asyncio.gather(
            self.generate_summary(profile, keywords, title),
            self.infer_salary(profile.years_of_experience or len(experience), location, company),
            self.rewrite_bullets(bullets_only[:20], keywords, target_role=title, target_company=company, jd_summary=jd_summary),
        )

        candidate_name = (profile.full_name or "").strip()
        cover_letter = await self._call_haiku(
            f"Write a concise 3-paragraph cover letter for {title} at {company}.\n"
            f"The candidate's name is {candidate_name}.\n"
            f"Opening: show genuine interest in the company and role.\n"
            f"Middle: highlight 2-3 specific achievements from their experience that directly match the role.\n"
            f"Closing: express enthusiasm and salary expectation of {salary}.\n"
            f"Candidate skills: {', '.join((profile.skills or [])[:10])}.\n"
            f"JD keywords to address: {', '.join(keywords[:8])}.\n"
            f"End the letter with 'Sincerely,' on one line, then '{candidate_name}' on the next line. "
            f"Do NOT use placeholders like [Your Name] — use the actual name above.\n"
            f"Return plain text only, no markdown.",
            max_tokens=500,
        )

        # --- Map rewritten bullets back to jobs ---
        rewritten_by_job: dict[int, list[str]] = {}
        for idx, (job_idx, _) in enumerate(bullet_pairs[:20]):
            rewritten_by_job.setdefault(job_idx, []).append(
                rewritten[idx] if idx < len(rewritten) else bullets_only[idx]
            )

        # --- Build HTML and generate PDF ---
        html = self._build_html(
            profile=profile,
            experience=experience,
            rewritten_by_job=rewritten_by_job,
            keywords=keywords,
            top_competencies=top_competencies,
            summary=summary,
            salary=salary,
            resume_skills=resume_skills,
        )

        import re
        def slugify(s: str) -> str:
            s = s.strip().lower()
            s = re.sub(r'[^a-z0-9]+', '_', s)
            return s.strip('_')[:40]

        name_slug = slugify(profile.full_name or "candidate")
        role_slug = slugify(title)
        company_slug = slugify(company)
        pdf_filename = f"{name_slug}_{role_slug}_{company_slug}.pdf"
        pdf_path = RESUMES_DIR / pdf_filename
        await asyncio.to_thread(self._generate_pdf_sync, html, pdf_path)

        application = Application(
            id=str(uuid.uuid4()),
            campaign_id=listing.campaign_id,
            job_listing_id=listing.id,
            user_id=user_id,
            tailored_resume_pdf_url=str(pdf_path),
            cover_letter=cover_letter,
            form_answers={
                "salary": salary,
                "summary": summary,
                "rewritten_bullets": rewritten,
                "top_competencies": top_competencies,
            },
            status="tailored",
        )
        listing.status = "applying"
        self.db.add(application)
        await self.db.commit()
        return application
