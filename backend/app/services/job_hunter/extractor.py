# backend/app/services/job_hunter/extractor.py
"""
Format-agnostic local extraction using spaCy NER + regex.
No LLM calls. Works on CV, portfolio narrative, LinkedIn export, plain text, PDF dump.

Strategy:
  - Contact info  → regex (universal patterns)
  - Skills        → taxonomy scan (universal)
  - Name          → PERSON entity at doc top, no format assumptions
  - Location      → GPE entities near doc top
  - Work exp      → ORG entities that co-occur with DATE entities nearby
  - Achievements  → any sentence/bullet containing numeric signals
  - Projects      → ORG/product mentions with tech terms but no adjacent dates
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-load spaCy so import cost is zero until first use
# ---------------------------------------------------------------------------
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("extractor: en_core_web_sm not found, running spacy download")
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
    return _nlp

# ---------------------------------------------------------------------------
# Skills taxonomy — add more as needed
# ---------------------------------------------------------------------------
_SKILLS = {
    "Python","TypeScript","JavaScript","Dart","SQL","Ruby","Go","Rust","Java","C++","C#","Swift","Kotlin",
    "Flutter","React","React Native","Next.js","Tailwind CSS","Electron","Zustand","HTML","CSS","Vue","Angular","Svelte",
    "Rails","Rails 8","FastAPI","Django","Express.js","Node.js","Spring","Laravel","Flask","Phoenix","Gin",
    "Claude API","Gemini API","OpenAI Whisper","MediaPipe","ONNX Runtime","PyTorch","TensorFlow","LangChain",
    "BERT","DistilBERT","all-MiniLM","InsightFace","GFPGAN","OpenCV","scikit-learn","NumPy","Pandas","Hugging Face",
    "PostgreSQL","MySQL","Redis","Neo4j","SQLite","MongoDB","DynamoDB","Cassandra","Elasticsearch","Pinecone",
    "Docker","Kubernetes","Celery","RabbitMQ","Solid Queue","AWS S3","AWS","GCP","Azure","Firebase",
    "GitHub Actions","CI/CD","Terraform","Ansible","Nginx","Linux",
    "Alembic","SQLAlchemy","Prisma","TypeORM","Sequelize",
    "Git","Playwright","FFmpeg","JWT","WebSocket","ActionCable","Solid Cable","Jitsi","Rack::Attack",
    "CUDA","CoreML","DirectML","ROCm","OpenVINO",
    "Win32 API","RabbitMQ","Crawlee","JobSpy","Stripe","Google Pay","M-Pesa","M-Pesa/Daraja","Daraja",
    "Zustand","Tailwind","Electron","Alembic","structlog","pytest","asyncio",
}
_SKILLS_LOWER = {s.lower(): s for s in _SKILLS}

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------
_EMAIL    = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}')
_PHONE    = re.compile(r'\+?[\d][\d\s\-().]{7,}')
_LINKEDIN = re.compile(r'linkedin\.com/in/[\w-]+', re.I)
_GITHUB   = re.compile(r'github\.com/[\w-]+', re.I)
_PORTFOLIO= re.compile(r'\*\*Portfolio:\*\*\s*([^\s\n]+)', re.I)
_YEARS_EXP= re.compile(r'(\d+)\+?\s*years?\s*of\s*(?:professional\s*)?experience', re.I)
_METRIC   = re.compile(r'\d[\d,.]*\s*(?:%|ms|s\b|K\b|M\b|B\b|\+|x\b)?|[$€£¥]\d|\b\d{4}\b')
_DATE_NEAR= re.compile(
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}'
    r'|\b(?:19|20)\d{2}\b'
    r'|\bPresent\b|\bCurrent\b', re.I
)
_BULLET   = re.compile(r'^\s*[-*•]\s+(.+)', re.M)
_SECTION_SKIP = re.compile(
    r'^\*\*[\w /]+:\*\*\s*[\w ,./+]+$'  # "**Stack:** Python, Rails" style lines
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(text: str) -> dict:
    """
    Extract structured profile data from any free-form text.
    Returns a dict with the same keys as CampaignProfile expects.
    """
    result: dict = {}

    result.update(_contact(text))
    result.update(_name_location(text))

    yoe = _years_exp(text)
    if yoe:
        result["years_of_experience"] = yoe

    result["skills"]          = _skills(text)
    result["work_experience"]  = _work_experience(text)
    result["achievements"]     = _achievements(text)
    result["projects"]         = _projects(text)

    return result


def merge(base: dict, incoming: dict) -> dict:
    """
    Merge incoming extracted data into base (existing profile data).
    Scalar fields: only set if not already present.
    List fields: union/append without duplicates.
    """
    result = dict(base)

    for key in ("full_name","email","phone","city","country",
                "linkedin_url","github_url","portfolio_url","years_of_experience"):
        if incoming.get(key) and not result.get(key):
            result[key] = incoming[key]

    # Skills: union
    existing_skills = set(result.get("skills") or [])
    result["skills"] = sorted(existing_skills | set(incoming.get("skills") or []))

    # Work experience: merge by company identity
    existing_we = result.get("work_experience") or []
    existing_companies = {j.get("company","").lower() for j in existing_we}
    for job in (incoming.get("work_experience") or []):
        if job.get("company","").lower() not in existing_companies:
            existing_we.append(job)
            existing_companies.add(job.get("company","").lower())
    result["work_experience"] = existing_we

    # Projects: merge by name identity
    existing_proj = result.get("projects") or []
    existing_names = {p.get("name","").lower() for p in existing_proj}
    for proj in (incoming.get("projects") or []):
        if proj.get("name","").lower() not in existing_names:
            existing_proj.append(proj)
            existing_names.add(proj.get("name","").lower())
    result["projects"] = existing_proj

    # Achievements: append unique
    existing_ach = set(result.get("achievements") or [])
    for a in (incoming.get("achievements") or []):
        if a not in existing_ach:
            existing_ach.add(a)
            (result.setdefault("achievements", [])).append(a)

    return result


# ---------------------------------------------------------------------------
# Internal extractors
# ---------------------------------------------------------------------------

def _contact(text: str) -> dict:
    out = {}
    m = _EMAIL.search(text)
    if m:
        out["email"] = m.group()
    m = _PHONE.search(text)
    if m:
        raw = m.group().strip()
        if sum(c.isdigit() for c in raw) >= 7:
            out["phone"] = raw
    m = _LINKEDIN.search(text)
    if m:
        out["linkedin_url"] = m.group()
    m = _GITHUB.search(text)
    if m:
        out["github_url"] = m.group()
    m = _PORTFOLIO.search(text)
    if m:
        out["portfolio_url"] = m.group(1).strip()
    return out


def _name_location(text: str) -> dict:
    out = {}
    nlp = _get_nlp()

    # Only scan the first 1500 chars — names and locations are almost always at the top
    doc = nlp(text[:1500])

    # PERSON entity — skip single-word hits that look like headings ("CV", "Summary")
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name = ent.text.strip()
            words = name.split()
            if len(words) >= 2 and all(w[0].isupper() for w in words if w):
                out["full_name"] = name
                break

    # GPE (geo-political entity) for city/country — take first two
    gpes = [ent.text.strip() for ent in doc.ents if ent.label_ == "GPE"]
    if gpes:
        out["city"] = gpes[0]
    if len(gpes) >= 2:
        out["country"] = gpes[1]

    # Explicit **Location:** line overrides NER (more reliable when present)
    loc = re.search(r'\*\*Location:\*\*\s*(.+)', text)
    if loc:
        parts = [p.strip() for p in loc.group(1).split(',')]
        out["city"] = parts[0]
        if len(parts) >= 2:
            out["country"] = parts[1]

    return out


def _years_exp(text: str) -> Optional[int]:
    m = _YEARS_EXP.search(text)
    return int(m.group(1)) if m else None


def _skills(text: str) -> list[str]:
    found = set()
    text_lower = text.lower()
    for skill_lower, canonical in _SKILLS_LOWER.items():
        pattern = r'(?<![a-z0-9/])' + re.escape(skill_lower) + r'(?![a-z0-9/])'
        if re.search(pattern, text_lower):
            found.add(canonical)
    return sorted(found)


_TECH_SINGLE_WORDS = {
    "api", "sdk", "orm", "ocr", "llm", "gpt", "ai", "ml", "ui", "ux",
    "rest", "http", "https", "json", "xml", "csv", "pdf", "url",
    "cpu", "gpu", "ram", "ssd", "aws", "gcp", "cdn", "dns", "tcp",
    "sql", "nosql", "cli", "gui", "ide", "vcs", "git", "jwt",
    "websocket", "oauth", "saas", "paas", "iaas",
    "pii", "phi", "gdpr", "soc", "iso", "sla", "kpi", "roi", "mvc",
    "oop", "ddd", "tdd", "bdd", "etl", "elt", "olap", "oltp",
    # common terms spaCy misclassifies as ORG
    "devops", "devsecops", "mlops", "dataops", "gitops",
    "backend", "frontend", "fullstack", "microservices",
    "github", "gitlab", "bitbucket", "jira", "confluence", "slack",
    "k-means", "kmeans", "xgboost", "lightgbm", "sklearn",
    "tkinter", "customtkinter", "tkinter",
    "talking",  # "Africa's Talking" partial match
}

# Known partial-name fragments that should never be treated as companies alone
_COMPANY_BLACKLIST_FRAGMENTS = {
    "startup",  # "Microsoft Startup" is not a company
    "engines",  # "Rails Engines"
    "talking",  # "Talking" extracted from "Africa's Talking"
}


def _is_real_company(name: str) -> bool:
    """
    Reject spaCy ORG entities that are actually tech terms, symbols, or markdown labels.
    Returns True only if the name looks like a real company/organisation.
    """
    name = name.strip()

    # Too short or pure symbols/punctuation
    if len(name) < 3:
        return False
    if re.match(r'^[^a-zA-Z]+$', name):
        return False

    # Must start with a letter
    if not name[0].isalpha():
        return False

    # Looks like a markdown label ("Architecture:", "Key decisions:", "**Stack:**")
    if re.search(r':\s*$|\*\*', name):
        return False

    # Contains flow/list operators — these are tech stacks or diagram labels, not companies
    # e.g. "ActionCable + Solid Cable", "OCR → risk", "companies ↔ managers"
    if re.search(r'[+→←↔]|->|<-|=>|<=', name):
        return False

    # All-uppercase acronym (PII, OCR, API, SQL, ML, etc.)
    if name.isupper() and len(name) <= 6:
        return False

    # Whole name is a known skill
    if name.lower() in _SKILLS_LOWER:
        return False

    # Single-word tech term
    if name.lower() in _TECH_SINGLE_WORDS:
        return False

    # Any individual word in the name is a known skill or tech term
    # Catches "Zustand 5", "BERT embeddings", "Google Pay", compound skill names
    words = re.split(r'[\s/]', name)
    for word in words:
        word_lower = word.lower().rstrip('s')  # naive depluralize
        if word_lower in _SKILLS_LOWER or word_lower in _TECH_SINGLE_WORDS:
            return False
        # Fragment-only company names (e.g. "Engines" from "Rails Engines", "Startup")
        if word_lower in _COMPANY_BLACKLIST_FRAGMENTS:
            return False

    # Pure version strings or numbers ("v2", "3.0", "2024")
    if re.match(r'^v?\d[\d.]*$', name):
        return False

    return True


def _work_experience(text: str) -> list[dict]:
    """
    Find ORG entities that co-occur with DATE entities within a ±300-char window.
    That signal is format-agnostic: any CV format that mentions a company and dates
    near each other is a job entry.
    """
    nlp = _get_nlp()
    doc = nlp(text)

    orgs  = [(e.text, e.start_char, e.end_char) for e in doc.ents if e.label_ == "ORG"]
    dates = [(e.text, e.start_char, e.end_char) for e in doc.ents if e.label_ == "DATE"]

    jobs = []
    seen_companies = set()

    for org_text, org_start, org_end in orgs:
        # Filter out tech terms, symbols, and other non-company ORG entities
        if not _is_real_company(org_text):
            continue

        # Find dates within 300 chars of this ORG
        nearby_dates = [
            d for d in dates
            if abs(d[1] - org_start) < 300
        ]
        if not nearby_dates:
            continue

        company = org_text.strip()
        if company.lower() in seen_companies:
            continue
        seen_companies.add(company.lower())

        # Extract date values
        date_texts = [d[0] for d in nearby_dates]
        start_date = date_texts[0] if date_texts else None
        end_date   = date_texts[1] if len(date_texts) > 1 else (
            "Present" if any(re.search(r'present|current', d, re.I) for d in date_texts) else None
        )

        # Grab surrounding text as the job body (500 chars after the ORG mention)
        body_start = min(org_start, nearby_dates[0][1])
        body_text  = text[body_start: body_start + 800]

        # Extract title: look for bold text or PERSON+TITLE near org
        title = _extract_title(body_text, doc, org_start)

        # Extract location from GPE entities near org
        gpes = [
            e.text for e in doc.ents
            if e.label_ == "GPE" and abs(e.start_char - org_start) < 200
        ]
        location = ", ".join(gpes[:2]) if gpes else None

        # Extract bullet responsibilities from the body
        bullets = [
            b.strip() for b in _BULLET.findall(body_text)
            if len(b.strip()) > 20 and not _SECTION_SKIP.match(b.strip())
        ]

        jobs.append({
            "title":            title,
            "company":          company,
            "location":         location,
            "start_date":       start_date,
            "end_date":         end_date,
            "responsibilities": bullets,
        })

    return jobs


def _extract_title(body: str, doc, org_char: int) -> Optional[str]:
    # Look for bold markdown title near the org
    bold = re.search(r'\*\*([^*]{3,60})\*\*', body)
    if bold:
        candidate = bold.group(1).strip()
        # Must look like a job title (not a stack/label)
        if not re.search(r'Stack:|Location:|Email:|Phone:', candidate, re.I):
            return candidate

    # Fallback: spaCy TITLE-like token sequence near org position
    for token in doc:
        if abs(token.idx - org_char) < 150 and token.ent_type_ in ("TITLE", "PERSON"):
            span_end = min(token.idx + 80, len(doc.text))
            line = doc.text[token.idx:span_end].split('\n')[0].strip()
            if 3 < len(line) < 80:
                return line

    return None


def _achievements(text: str) -> list[str]:
    """Bullets and sentences containing numeric/metric signals."""
    results = []
    seen = set()

    # From bullet points
    for b in _BULLET.findall(text):
        b = b.strip()
        if _SECTION_SKIP.match(b):
            continue
        if _METRIC.search(b) and b not in seen:
            results.append(b)
            seen.add(b)

    # From non-bullet sentences with strong metrics
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('-') or line.startswith('*') or line.startswith('#'):
            continue
        if len(line) > 30 and _METRIC.search(line) and line not in seen:
            # Must have a verb-like signal to be a real achievement sentence
            if re.search(r'\b(built|led|designed|reduced|increased|shipped|launched|grew|achieved|optimized|scaled|managed|integrated|deployed|created|saved|generated)\b', line, re.I):
                results.append(line)
                seen.add(line)

    return results


def _projects(text: str) -> list[dict]:
    """
    Find named things (ORG entities or capitalized multi-word phrases) that have
    tech terms nearby but no date co-occurrence — those are projects, not jobs.
    """
    nlp = _get_nlp()
    doc = nlp(text)

    date_positions = {e.start_char for e in doc.ents if e.label_ == "DATE"}

    projects = []
    seen = set()

    # Also scan for explicit project-like headings (### Name or ## Name)
    for m in re.finditer(r'#{2,3}\s+(.+)', text):
        heading = m.group(1).strip()
        # Skip section headers
        if re.match(r'^(Work Experience|Education|Skills|Projects|Summary|Contact|Certifications)', heading, re.I):
            continue
        if heading.lower() in seen:
            continue

        body_start = m.end()
        body_end   = body_start + 800
        body       = text[body_start:body_end]

        # Has a tech stack signal?
        skills_found = _skills(heading + " " + body)
        if not skills_found:
            continue

        # No dates nearby → it's a project, not a job
        has_dates = any(abs(d - m.start()) < 400 for d in date_positions)
        if has_dates:
            continue

        # Description: first substantial non-heading, non-bullet line
        desc_lines = [
            l.strip() for l in body.split('\n')
            if l.strip() and not l.strip().startswith('#')
            and not l.strip().startswith('**Stack')
            and not l.strip().startswith('- ')
            and len(l.strip()) > 20
        ]
        description = desc_lines[0] if desc_lines else ""

        # Tech stack from **Stack:** line or skills found in body
        stack_match = re.search(r'\*\*Stack[:\s]+\*\*\s*(.+)|\*\*Stack:\*\*\s*(.+)', body)
        if stack_match:
            raw_stack = (stack_match.group(1) or stack_match.group(2) or "").strip()
            tech_stack = [t.strip() for t in re.split(r'[,;]', raw_stack) if t.strip()]
        else:
            tech_stack = skills_found[:15]

        projects.append({
            "name":        heading,
            "description": description,
            "tech_stack":  tech_stack,
            "link":        None,
        })
        seen.add(heading.lower())

    return projects
