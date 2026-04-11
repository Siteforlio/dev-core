# Developer Core — Job Hunter Module: Design Spec
**Date:** 2026-04-11
**Status:** Approved
**Platform:** Cross-platform Desktop (Windows, macOS, Linux)

---

## 1. Vision

A fully automated job search engine that applies to 100+ jobs per day, tailors every resume to 90%+ keyword match, monitors email around the clock, schedules interviews to calendar, and bridges directly into the existing Interview Prep module — all without the user lifting a finger after setup.

The system fits the candidate to the role, not the other way around. The user's skills define which roles are in scope. The AI speaks each job's language, never invents experience, and operates at scale without human approval gates.

---

## 2. Core Principles

- **Fit the candidate to the role:** The user's skills determine job scope. The AI adapts the resume vocabulary to each JD — it never inflates or invents.
- **Fully automated:** No approval gates. Once a campaign is active, it runs without user intervention.
- **Cost-efficient:** Claude Haiku for all LLM work (filtering + tailoring). This overrides the project-default `claude-sonnet-4-6` for cost reasons — Haiku is sufficient for structured extraction and rewriting tasks. Target: < $5/month at 100 jobs/day.
- **Scalable by design:** Stateless FastAPI workers, Celery task queue, Redis for state — built for 5,000 concurrent users from day one.
- **Integrated, not duplicated:** The Interview Prep bridge calls existing `PersonaEngine` and `manager_queries` — no new graph infrastructure, no changes to existing Interview Prep routes.
- **Universal email + calendar:** IMAP/SMTP for all email providers (Gmail, Outlook, Apple Mail). CalDAV for all calendar providers (Google, Apple, Outlook).

---

## 3. Architecture

### 3.1 High-Level

```
[Electron Shell]
  ├── Job Hunter UI (campaign manager, profile onboarding, dashboard)
  └── IPC bridge → FastAPI backend

[FastAPI Backend — job_hunter module]
  ├── Campaign Service      — campaign CRUD, activation, sub-category inference
  ├── Profile Service       — completeness validation, resume parsing, field extraction
  ├── Scraper Service       — JobSpy + Crawlee orchestration, dedup, filtering
  ├── Tailor Service        — Haiku JD analysis, resume rewriting, PDF generation
  ├── Apply Service         — Playwright ATS form filling and submission
  ├── Email Service         — IMAP monitoring, classification, SMTP replies
  ├── Calendar Service      — CalDAV event creation
  ├── Dashboard Service     — aggregated stats and pipeline view
  └── Bridge Service        — Interview Prep context handoff

[Background Workers — Celery + Redis]
  ├── scraper_worker        — runs every 6 hours per active campaign (Celery Beat)
  ├── tailor_worker         — triggered per job listing after scrape (Celery task)
  ├── apply_worker          — triggered per tailored application (Celery task)
  └── email_worker          — runs every 60 seconds via Celery Beat (always-on polling)

[Real-time Activity Feed]
  └── Celery worker → Redis pub/sub → FastAPI WebSocket (/ws/campaign/{id}/activity)
      → Frontend subscribes per active campaign (same pattern as emotion feed)

[Existing Infrastructure — reused, not rebuilt]
  ├── PostgreSQL            — all job hunter relational data
  ├── Redis                 — Celery broker + result backend, campaign queue state, rate limiting, pub/sub
  ├── Neo4j                 — company + manager graph (read-only from job hunter)
  └── PersonaEngine         — existing service, called by bridge_service
```

### 3.2 Celery Architecture

Celery is not in the existing stack and must be added. Key decisions:

- **Broker + result backend:** Redis (already in stack) — both broker and results use the same Redis instance with separate key namespaces (`celery:broker:*`, `celery:results:*`)
- **Async compatibility:** Celery tasks are synchronous by default. All job hunter Celery tasks use a `run_async` wrapper: `asyncio.run(async_fn(...))` inside the sync task body. This is the same pattern as FastAPI's `run_in_executor` for CPU-bound work — keeps the async service layer intact without requiring `celery[gevent]`.
- **Email worker pattern:** Celery Beat periodic task with 60-second interval — not a long-running blocking task. Each invocation polls IMAP, processes new emails, and exits. Idempotent by design.
- **Scraper worker pattern:** Celery Beat periodic task with configurable interval (default 6 hours per campaign). Campaign ID passed as task argument.
- **Worker concurrency:** Maximum 4 Playwright subprocesses per worker instance (Celery `concurrency=4`). At scale, multiple worker instances run behind a shared Redis broker — stateless and horizontally scalable.
- **ARCHITECTURE.md must be updated** to add Celery to the tech stack table before Step 1 is built.

### 3.3 Integration with Interview Prep

The Job Hunter module **only reads** from the Interview Prep graph infrastructure. When an interview is detected:

```
email_worker detects interview invite
  → application_id → job_listings → company + role
  → bridge_service calls PersonaEngine.get_context(company, role, round_type="HR")
  → returns structured dict: {managers, round_patterns, persona_string}
  → Interview Prep session opens with this context pre-loaded
```

**`PersonaEngine.get_context()`** is a new thin method added to the existing `PersonaEngine` class. It returns the intermediate `manager_context` dict alongside the final persona string — allowing the bridge to surface structured manager/round data to the UI rather than only the collapsed string.

Implementation path (Step 10): extract a private `_assemble_context(company, role, round_type)` helper from `build()` that performs the graph calls and returns the `manager_context` dict. Both `build()` and `get_context()` delegate to this helper. `build()` continues to return a `str` — its signature and return type are unchanged, and no existing callers break. This is the only implementation path that avoids duplicating graph queries.

`company_queries` is **not** used in the bridge. `PersonaEngine` relies on `manager_queries` and `round_queries` only.

---

## 4. Data Model (PostgreSQL)

All job hunter tables follow existing SQLAlchemy + Alembic conventions from ARCHITECTURE.md. All migrations are reversible. Indexes are explicit. Soft deletes (`deleted_at`) on tables with audit value.

```
job_hunter_profiles
  id, user_id (FK users), is_complete (bool), completion_score (int 0-100)
  work_experience (JSONB), education (JSONB), skills (JSONB)
  projects (JSONB), languages_spoken (JSONB)
  github_url, linkedin_url, portfolio_url
  updated_at, deleted_at
  INDEX: (user_id)

job_hunter_campaigns
  id, user_id (FK users), name, status (active/paused/completed)
  broad_category, sub_categories (JSONB)
  profile_overrides (JSONB)
  email_account_encrypted (TEXT)     -- Fernet-encrypted IMAP credentials (see Section 15)
  caldav_account_encrypted (TEXT)    -- Fernet-encrypted CalDAV credentials
  email_monitor_since (timestamp)
  schedule_interval_hours (int, default 6)
  user_country (TEXT)                -- user's current country, set at campaign creation
  created_at, last_run_at, deleted_at
  INDEX: (user_id), (user_id, status)

job_listings
  id, campaign_id (FK), source (jobspy/crawlee/greenhouse)
  title, company, location, remote (bool), url, apply_url
  description, match_score, sub_category
  url_hash (TEXT, UNIQUE per user_id)   -- SHA-256 of (company + title + apply_url), enforced unique at DB level
  discovered_at, deleted_at
  status (pending/tailoring/applying/applied/skipped/failed)
  INDEX: (campaign_id, status), (campaign_id, sub_category), (url_hash)

applications
  id, campaign_id (FK), job_listing_id (FK), user_id (FK)
  tailored_resume_pdf_url, cover_letter, form_answers (JSONB)
  status (applied/responded/interview/offer/rejected/withdrawn/failed)
  applied_at, status_updated_at, deleted_at
  INDEX: (user_id, status), (job_listing_id), (campaign_id)

email_events
  id, application_id (FK, nullable), campaign_id (FK)
  type (interview/rejection/other)
  subject, sender, received_at, raw_snippet
  ai_reply_sent (bool), ai_reply_body, ai_reply_sent_at
  INDEX: (campaign_id, type), (application_id)

calendar_events
  id, application_id (FK), email_event_id (FK)
  title, scheduled_at, duration_minutes
  calendar_provider (google/apple/outlook)
  external_event_id, created_at
  INDEX: (application_id)
```

### Deduplication

Job deduplication uses a `url_hash` column: `SHA-256(user_id + company + title + apply_url)`. Stored as a `UNIQUE` constraint in PostgreSQL — enforced at the DB level, not in Redis. This is permanent and correct for audit purposes. No TTL required.

---

## 5. Profile Completeness System

Before any campaign can activate, the profile must pass a completeness check. The AI conducts the onboarding conversation — asks for missing fields one section at a time and stops only when every required section is filled.

### Required fields (hard blocks — campaign cannot start without these):

| Section | Fields |
|---|---|
| Contact | Full name, email, phone, city, country, LinkedIn URL, GitHub URL |
| Work Experience | Min 1 entry: company, title, start date, end date or "Present", responsibilities |
| Education | Min 1 entry: degree, institution, field of study, graduation year |
| Skills | Min 3: programming languages, frameworks, tools |
| Projects | Min 1 entry: name, description, tech stack, link |
| Languages Spoken | Min 1: language + proficiency level |

### AI-inferred (never stored on profile — generated fresh per application):

- Professional summary (tailored to each JD)
- Salary expectation (inferred from seniority + role location + company size)
- Rewritten experience bullets (keyword-matched to JD)
- Cover letter / ATS form answers

### Sub-category inference (run once at campaign creation, stored on campaign):

```
profile.skills → Claude Haiku → sub_categories[]

Example:
  skills: [Flutter, Dart, Firebase, Django, PostgreSQL, React]
  broad_category: "Software Engineering"
  → sub_categories: ["Mobile Development", "Backend Engineering", "Full Stack"]
```

---

## 6. Job Discovery Pipeline

### Sources (in priority order):

| Source | What it covers | Method |
|---|---|---|
| JobSpy | Google Jobs, LinkedIn, Indeed, Glassdoor, ZipRecruiter | Python library, no credentials |
| Crawlee (Playwright) | Greenhouse, Lever, Ashby, Workday, direct company portals | Browser automation |
| Greenhouse API | Greenhouse-hosted companies (structured JSON) | `boards-api.greenhouse.io/v1/boards/{slug}/jobs` |

### Filtering logic:

```
job.title + job.description → Haiku scoring prompt
  → does this role's core requirement match user's sub_categories?
  → score: MATCH / PARTIAL / SKIP
  → SKIP jobs are discarded, MATCH and PARTIAL queued for tailoring
```

### Remote preference rule (applied before Haiku scoring — hard filter, no LLM needed):

```
if job.remote == true → KEEP (always)
if job.remote == false:
    if job.location_country == campaign.user_country → KEEP (hybrid/onsite allowed)
    else → SKIP (never apply to onsite/hybrid roles in another country)
```

Country comparison is normalised to ISO 3166-1 alpha-2 codes. Location parsing uses the job's `location` field; ambiguous locations default to SKIP (safer than applying to a role the user can't attend).

### Anti-ban strategy (Crawlee):

- Per-domain request throttling — respects rate limits
- Randomised browser fingerprints (OS, locale, viewport) via Crawlee's `PlaywrightCrawler`
- Proxy rotation via `ProxyConfiguration` — tiered (cheap proxies first, escalate on block)
- Human-like delays between requests

### What is never scraped:
- LinkedIn Easy Apply postings (requires credentials, high ban risk — skipped at the filter stage by checking for `linkedin.com/jobs/apply` in `apply_url`)

---

## 7. Resume Tailoring Pipeline

Each matched job triggers a Haiku tailoring task:

```
1. Extract JD keywords       → top 15-20 ATS keywords from job description
2. Map to profile             → which skills + experience lines match each keyword
3. Rewrite bullets            → reformulate existing bullets using JD vocabulary
                                (never invents — only reformulates real experience)
4. Reorder skills             → surface most-relevant skills first
5. Generate summary           → 2-3 sentence professional summary matching JD tone
6. Infer salary               → based on seniority + location + company signals
7. Generate PDF               → HTML template → Playwright headless → PDF
8. ATS compliance check       → single column, no tables-in-tables, text-selectable
```

**Cost target:** < $0.003 per application at Haiku pricing.

---

## 8. Auto-Apply Engine

Crawlee + Playwright navigates to `apply_url` and fills the ATS form:

### Supported ATS platforms (priority order):
- Greenhouse (most common, clean form structure)
- Lever
- Ashby
- Workday (more complex, higher bot-detection — handled via fingerprinting)
- Generic HTML forms (fallback)

### Per-application flow:
```
1. Navigate to apply_url
2. Detect ATS platform from DOM/URL patterns
3. Fill standard fields (name, email, phone, location, LinkedIn, GitHub)
4. Upload tailored resume PDF
5. Answer additional questions using Haiku (cover letter, "why this company", salary)
6. Submit form
7. Log to applications table: status = "applied", timestamp, form_answers snapshot
8. On error: log failure reason, mark job_listing.status = "failed" and
   application.status = "failed", do not retry automatically
```

### Playwright concurrency:
- Maximum 4 concurrent Playwright subprocesses per Celery worker instance
- Configurable via `PLAYWRIGHT_MAX_CONCURRENCY` env var
- At 5,000 campaigns, multiple worker instances scale horizontally behind the shared Redis broker

---

## 9. Email Intelligence

Email monitoring runs as a **Celery Beat periodic task every 60 seconds** — independent of the 6-hour scrape schedule. Each invocation is stateless and idempotent.

### Connection:
- **Protocol:** IMAP (read) + SMTP (send) — universal across Gmail, Outlook, Apple Mail, Yahoo
- **Auth:** Fernet-encrypted credentials in `job_hunter_campaigns.email_account_encrypted` (see Section 15)
- **Scope:** Only emails received after `campaign.email_monitor_since` are processed

### Classification:
```
Email subject + snippet → Haiku classifier
  → type: "interview" | "rejection" | "other"
  → company match: fuzzy match against active applications
  → application_id resolved (or null if unmatched)
```

### On interview detected:
```
1. Update application.status = "interview"
2. Create email_event record (type = "interview")
3. Extract date/time from email body → create calendar_event
4. Publish to Redis pub/sub channel: campaign:{id}:activity
5. Mark in dashboard: interview scheduled, company, date
6. Enable "Start Interview Prep" button for this application
```

### On rejection detected:
```
1. Update application.status = "rejected"
2. Create email_event record (type = "rejection")
3. Generate AI reply via Haiku:
   - Tone: professional, gracious, curious
   - Content: thank them, ask for specific feedback, ask what would make a stronger candidate
4. Send reply via SMTP
5. Log ai_reply_body + ai_reply_sent_at
6. Publish to Redis pub/sub channel: campaign:{id}:activity
```

---

## 10. Calendar Sync

**Protocol:** CalDAV — universal across Google Calendar, Apple Calendar, Outlook Calendar.

```
interview email detected
  → extract: date, time, duration, company name, role
  → create iCalendar event (.ics format)
  → push to user's CalDAV endpoint (credentials from caldav_account_encrypted)
  → store external_event_id in calendar_events table
```

User connects their calendar once during campaign setup (CalDAV URL + credentials). Works with any CalDAV-compatible provider. Step 8 depends on Step 7 being fully operational — the success gate for Step 8 is only verifiable after Step 7's IMAP detection is working.

---

## 11. Dashboard

Two-panel layout per campaign: summary strip at top, full pipeline below.

### Summary strip:
- Applications sent (today / this week / total)
- Responses received
- Interviews scheduled
- Offers received
- Rejection rate

### Full pipeline (per application):
```
[Company] [Job title] [Location] [Applied at]
[Status badge: Applied / Responded / Interview / Offer / Rejected / Failed]
[Match score] [Source] [→ View tailored resume] [→ View email thread]
```

### Interview panel:
- Interview date + time (from calendar event)
- Company + role
- **"Start Interview Prep"** button — calls bridge_service, launches Interview Prep module

### AI activity log (real-time):
- Frontend opens WebSocket to `/api/v1/ws/campaign/{id}/activity`
- FastAPI WebSocket handler subscribes to Redis pub/sub channel `campaign:{id}:activity`
- Celery workers publish activity strings to this channel after each action
- This is a new Redis pub/sub → WebSocket pattern, consistent with ARCHITECTURE.md Section 11 scaling principles (stateless workers, Redis for cross-instance coordination)

---

## 12. Interview Prep Bridge

When the user clicks "Start Interview Prep" from the dashboard:

```
application_id
  → job_listings: company, role
  → bridge_service.get_interview_context(company, role)
      → PersonaEngine.get_context(company=company, role=role, round_type="HR")
      → returns: {
            "managers": [...],         # from manager_queries
            "round_patterns": {...},   # from round_queries
            "persona_string": "..."    # the rendered persona prompt
         }
  → Interview Prep session opens with this structured context
```

**`PersonaEngine.get_context()`** is a new additive method on the existing `PersonaEngine` class. It extracts the `manager_context` dict that `build()` already assembles internally, adds the final persona string, and returns both. `build()` itself is unchanged. No existing callers break.

`company_queries` is **not used** in this flow. `PersonaEngine` uses `manager_queries` and `round_queries` only.

---

## 13. Build Steps

Each step is a puzzle piece that contributes to the full picture. No step is a standalone product — together they form the complete Job Hunter.

**Testing rule:** Every step must include unit tests for all new service-layer functions and integration tests for all new API routes. 80% coverage minimum on new code.

| Step | Piece | Success Gate |
|---|---|---|
| 1 | **Foundation** — PostgreSQL schema (all tables with indexes + soft deletes), Alembic migrations, Celery setup (Redis broker + result backend), Celery Beat config, email + CalDAV worker skeletons, ARCHITECTURE.md updated | Migrations run cleanly; Celery worker and Beat scheduler boot; Redis connection confirmed; `asyncio.run()` wrapper verified in a smoke-test task |
| 2 | **Profile onboarding** — chat interface + resume upload (PDF/DOCX parsing via `pdfplumber`/`python-docx`), completeness validator (all required fields), field storage to `job_hunter_profiles` | Completeness check correctly blocks incomplete profiles; all required sections present → `is_complete = true`; incomplete profile → specific missing fields returned |
| 3 | **Campaign setup** — campaign creation UI, broad category selection, AI sub-category inference via Haiku, profile overrides, campaign stored with `status = active` | Campaign created; sub-categories correctly inferred from skills (Flutter → Mobile Dev, Django → Backend); overrides stored and retrievable |
| 4 | **Job discovery** — JobSpy integration, Crawlee Playwright scraper, Greenhouse API, dedup via `url_hash` unique constraint, sub-category filtering, jobs stored to `job_listings` | 50+ jobs scraped and stored per campaign run; duplicate `url_hash` correctly rejected by DB; LinkedIn Easy Apply URLs filtered out |
| 5 | **Resume tailoring** — Haiku JD analysis, keyword extraction, bullet rewriting, PDF generation, ATS compliance check | Tailored PDF generated per job; keyword overlap ≥ 90% verified against JD; PDF is text-selectable (ATS compliant) |
| 6 | **Auto-apply engine** — Playwright fills and submits Greenhouse + Lever + Ashby forms, `application.status = "applied"` logged, `failed` status on error | Application submitted end-to-end on a real Greenhouse sandbox posting; status logged correctly; form failure sets `status = "failed"` not a crash |
| 7 | **Email intelligence** — IMAP polling (Celery Beat 60s), email classification via Haiku, rejection AI reply via SMTP, `application.status` updates, Redis pub/sub publish | Rejection email triggers AI reply within 5 minutes; interview email sets `status = "interview"`; activity event published to Redis channel |
| 8 | **Calendar sync** — CalDAV integration, interview event creation from email detection (requires Step 7 complete) | Interview email → calendar event created in user's calendar within 5 minutes of detection |
| 9 | **Dashboard** — campaign overview, application pipeline, email event log, real-time AI activity feed via WebSocket + Redis pub/sub | All application statuses visible; activity log updates in real time when worker publishes; interview panel shows scheduled date |
| 10 | **Interview prep bridge** — `PersonaEngine.get_context()` added to existing class, `bridge_service.py` calls it, "Start Interview Prep" button in dashboard triggers it | Clicking the button opens Interview Prep pre-loaded with correct company persona and manager signals; `build()` return value unchanged; no new graph queries added |

---

## 14. Tech Stack Additions

New dependencies added to the existing stack. ARCHITECTURE.md tech stack table must be updated in Step 1.

| Addition | Purpose |
|---|---|
| `jobspy` | Multi-source job scraping (Google Jobs, LinkedIn, Indeed, Glassdoor, ZipRecruiter) |
| `crawlee[playwright]` | ATS portal scraping with anti-bot fingerprinting and proxy rotation |
| `celery[redis]` | Background task queue + periodic scheduler; Redis as broker and result backend. Celery Beat is included in this package — no separate install needed. |
| `imaplib` + `smtplib` (stdlib) | IMAP email reading + SMTP sending — no extra dependency |
| `caldav` | CalDAV calendar sync (Google, Apple, Outlook) |
| `pdfplumber` | Resume PDF parsing during onboarding |
| `python-docx` | Resume DOCX parsing during onboarding |
| `cryptography` | Fernet symmetric encryption for email + CalDAV credentials |

---

## 15. Security & Cost Notes

### Credential encryption:
- Email and CalDAV credentials stored using **Fernet symmetric encryption** (`cryptography.fernet.Fernet`)
- Encryption key stored in environment variable `JOB_HUNTER_ENCRYPTION_KEY` (32-byte URL-safe base64)
- Key rotation requires re-encrypting all stored credentials — migration script must be provided when rotating
- Credentials never logged at any level

### Security:
- IMAP/SMTP connections use TLS
- Playwright runs in isolated subprocess per Celery worker — no shared browser state between users
- Proxy credentials in env vars, never committed or logged

### Cost target at scale:
- Haiku filtering: ~$0.03/day per campaign (100 jobs)
- Haiku tailoring: ~$0.08/day per campaign (40 matched jobs)
- **Total LLM cost: ~$0.11/day per campaign → ~$3.30/month per active campaign**
- Proxy costs (if needed for bot-resistant portals): ~$10–30/month — primary variable cost

---

## 16. Success Definition

The Job Hunter module succeeds when:
1. A user can create a campaign, complete their profile, and have 100+ applications submitted per day without touching the keyboard
2. Every submitted resume scores ≥ 90% keyword match against the target JD
3. Rejection emails receive an AI reply within 5 minutes of receipt
4. Interview invites are automatically added to the user's calendar
5. Clicking "Start Interview Prep" opens the existing module with company + manager context pre-loaded from Neo4j
6. The system handles 5,000 concurrent active campaigns without degradation
