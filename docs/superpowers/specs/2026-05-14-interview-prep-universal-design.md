# Developer Core — Interview Prep Universal Upgrade: Design Spec
**Date:** 2026-05-14
**Status:** Approved
**Supersedes:** `2026-04-09-interview-prep-design.md` (tech-centric v1)

---

## 1. Vision

Transform the existing tech-centric interview simulator into a universal career preparation platform — covering 10 career tracks, 5 seniority levels, and the full interview journey from phone screen to offer negotiation.

Users bring their real interview context (company, role, JD, hiring manager) and get a photorealistic mock session calibrated to their exact situation. Every session feeds a 3-layer improvement system that tracks their growth over time.

**Cost target:** Under $0.02 per session (DeepSeek API + local/free components).

---

## 2. Core Principles

- **Universal by default:** Any career, any level, any industry — not just tech.
- **Context injection:** A user with a real interview this week can prep for that exact scenario.
- **Cost-first AI:** DeepSeek-V3/R1 replace Claude entirely. Local Whisper + browser TTS = near-zero marginal cost.
- **Walking skeleton preserved:** Each build step ships a working product increment.
- **Data is the moat:** Community knowledge graph grows smarter with every session.

---

## 3. Career Path Taxonomy

### 3.1 Career Tracks (10)

| # | Track | Example Roles |
|---|---|---|
| 1 | Technology | SWE, Data Scientist, DevOps, PM, Cybersecurity |
| 2 | Finance & Fintech | Banking, Investment, Accounting, Financial Analysis, CFO/CTO |
| 3 | Healthcare | Nursing, Medical, Healthcare Admin, Pharmacy |
| 4 | Business & Consulting | Management Consulting, Strategy, Operations |
| 5 | Sales & Marketing | Sales, Digital Marketing, Brand Management |
| 6 | Design & Creative | UX/UI, Graphic Design, Product Design |
| 7 | Legal & Compliance | Corporate Law, Paralegal, Compliance, Risk |
| 8 | HR & People | Human Resources, Talent Acquisition, L&D |
| 9 | Education & Training | Teaching, Academic, Corporate Training |
| 10 | Operations & Supply Chain | Project Management, Logistics, Procurement |

### 3.2 Seniority Levels (5)

| Level | Label | Years Experience | Examples |
|---|---|---|---|
| 1 | Entry / Junior | 0–2 yrs | Junior Developer, Associate Analyst |
| 2 | Mid-level | 2–5 yrs | Software Engineer, Financial Analyst |
| 3 | Senior | 5–10 yrs | Senior Engineer, Senior Manager |
| 4 | Lead / Manager | People management | Engineering Manager, Team Lead |
| 5 | Director / VP / C-Suite | Executive | CTO, CFO, VP Engineering, Director |

### 3.3 Universal Interview Stages (8)

Not every stage applies to every track/level combination. The system maps relevant stages per combination.

| Stage | Description | Applies To |
|---|---|---|
| 1. Phone Screen | Recruiter fit check, 15–30 min | All tracks, all levels |
| 2. HR Interview | Culture, motivations, soft skills | All tracks, all levels |
| 3. Hiring Manager Interview | Role fit, team dynamics | All tracks, level 2+ |
| 4. Skills / Domain Interview | Role-specific competencies | All tracks, all levels |
| 5. Panel Interview | Cross-functional, multi-interviewer | All tracks, level 3+ |
| 6. Case / Presentation | Structured problem solving or deck | Consulting, level 3+, all C-suite |
| 7. Final / Executive Interview | C-suite alignment | Level 4+, strategic roles |
| 8. Offer Negotiation Prep | Salary, package, counter-offer | All tracks, all levels |

---

## 4. Knowledge Base Architecture

### 4.1 Knowledge Profile Structure

Stored as JSON in PostgreSQL. One profile per `career_track × seniority_level × interview_stage`.

```json
{
  "track": "finance_fintech",
  "level": "director_vp_csuite",
  "stage": "hiring_manager",

  "core_competencies": [
    "capital allocation",
    "regulatory compliance",
    "team leadership",
    "stakeholder communication",
    "risk management"
  ],

  "question_archetypes": [
    {
      "type": "behavioral",
      "framework": "STAR",
      "weight": 0.35,
      "example": "Tell me about a time you navigated regulatory pressure while maintaining growth targets."
    },
    {
      "type": "situational",
      "framework": "SOAR",
      "weight": 0.25,
      "example": "If our revenue dropped 30% next quarter, walk me through your response."
    },
    {
      "type": "domain",
      "framework": "open",
      "weight": 0.25,
      "example": "How do you think about Basel III in the context of a fintech operating under a bank charter?"
    },
    {
      "type": "leadership",
      "framework": "STAR",
      "weight": 0.15,
      "example": "Describe how you built and scaled a high-performing finance team."
    }
  ],

  "evaluation_rubrics": {
    "excellent": "Quantified business impact, strategic framing, stakeholder awareness, executive presence",
    "good": "Structured answer, relevant experience, some specifics, clear ownership",
    "needs_work": "Vague, no metrics, no ownership, overly tactical for level",
    "poor": "No structure, bad-mouths previous employer, no self-awareness"
  },

  "answer_frameworks": ["STAR", "SOAR", "MECE", "Pyramid Principle"],

  "common_pitfalls": [
    "Over-indexing on technical details, ignoring business impact",
    "Answering at junior level when senior framing is expected",
    "Not quantifying outcomes",
    "Forgetting to ask questions at the end"
  ],

  "red_flags": [
    "Bad-mouthing previous employer",
    "No questions for the interviewer",
    "Can't speak to business impact of technical decisions",
    "Inconsistent timeline in career narrative"
  ],

  "skill_dimensions": [
    "domain_knowledge",
    "communication_clarity",
    "quantified_impact",
    "executive_presence",
    "leadership_narrative",
    "culture_alignment"
  ]
}
```

### 4.2 Database Schema Addition

```sql
-- New table: career knowledge base profiles
CREATE TABLE knowledge_profiles (
  id            TEXT PRIMARY KEY,
  track         TEXT NOT NULL,
  level         TEXT NOT NULL,
  stage         TEXT NOT NULL,
  profile       JSONB NOT NULL,
  created_at    TIMESTAMP DEFAULT NOW(),
  updated_at    TIMESTAMP DEFAULT NOW(),
  UNIQUE(track, level, stage)
);

-- New table: user progress tracking across sessions
CREATE TABLE user_progress (
  id              TEXT PRIMARY KEY,
  user_id         TEXT REFERENCES users(id) NOT NULL,
  session_id      TEXT REFERENCES sessions(id) NOT NULL,
  career_track    TEXT NOT NULL,
  level           TEXT NOT NULL,
  stage           TEXT NOT NULL,
  skill_dimension TEXT NOT NULL,
  score           FLOAT NOT NULL,
  recorded_at     TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Context Injection System

### 5.1 Session Entry — What the User Provides

```
Company name:       "Stripe"             (required)
Role / title:       "CTO"                (required)
Career track:       "Finance & Fintech"  (auto-detected or user selects)
Seniority level:    "Director/VP/CSuite" (required)
Interview stage:    "Hiring Manager"     (required)
Job description:    [paste text]         (optional — enables JD-specific questions)
Hiring manager:     "Jane Doe"           (optional — enables persona from graph)
```

### 5.2 Context Assembly Pipeline (3 steps)

```
Step 1 — JD Analysis  (1 DeepSeek-V3 call, result cached by JD hash for 7 days)
  Input:  Raw JD text
  Output: {
    required_skills, preferred_skills,
    culture_signals, red_flags_from_jd,
    implied_seniority, key_responsibilities
  }

Step 2 — Context Assembly  (zero LLM calls — pure DB reads)
  Pull:   KnowledgeProfile for track × level × stage
  Pull:   Company signals from Neo4j community graph
  Pull:   Hiring manager persona from Neo4j (if name provided)
  Pull:   User's weak skill_dimensions from user_progress (last 5 sessions)
  Merge:  JD analysis overlaid on knowledge profile
  Output: ContextPackage

Step 3 — Question Generation  (1 DeepSeek-V3 call, cached per session)
  Input:  ContextPackage
  Output: 5 questions calibrated to role + company + stage + user weak areas
  Cache:  Redis key "{company}:{track}:{level}:{stage}" TTL 24h
```

### 5.3 Question Generation Prompt Structure

```
You are a {level} {role} interviewer at {company} conducting a {stage} interview.

Company context: {company_signals}
Role requirements: {jd_parsed.required_skills}
Culture signals: {jd_parsed.culture_signals}
Candidate level: {level}
Interview framework: {track_profile.answer_frameworks}
Focus on these skill dimensions (candidate is weak here): {user_weak_dimensions}

Generate 5 interview questions. Weight toward: {archetype_weights}.
Return JSON array of question strings only.
```

---

## 6. LLM Migration — Claude → DeepSeek

### 6.1 Model Strategy

| Task | Model | Cost Estimate |
|---|---|---|
| Question generation | deepseek-chat (V3) | ~$0.001/session |
| Answer grading | deepseek-chat (V3) | ~$0.001/answer |
| JD parsing | deepseek-chat (V3) | ~$0.001/JD (cached 7d) |
| Persona building | deepseek-chat (V3) | ~$0.001/session |
| Debrief analysis | deepseek-reasoner (R1) | ~$0.003/session |
| Improvement plan | deepseek-reasoner (R1) | ~$0.003/plan |

**Total per session: ~$0.01–0.02**

### 6.2 Code Change

DeepSeek uses the OpenAI-compatible API. Minimal code change:

```python
# backend/app/services/llm_orchestrator.py
import openai

class LLMOrchestrator:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self._model_fast = "deepseek-chat"       # DeepSeek-V3
        self._model_think = "deepseek-reasoner"  # DeepSeek-R1
```

No changes to method signatures. `DebriefService` uses `_model_think` for analysis.

### 6.3 .env Update

```
DEEPSEEK_API_KEY=your_key_here
# ANTHROPIC_API_KEY removed
```

---

## 7. Improvement System

### 7.1 Layer 1 — Real-Time Answer Feedback

After every answer, the grading response always returns:

```json
{
  "score": 7.5,
  "passed": true,
  "what_worked": "Strong use of quantified outcome — mentioned 40% cost reduction.",
  "what_was_missing": "Didn't address stakeholder alignment.",
  "stronger_version": "Add: 'I aligned CFO and CTO upfront to avoid sign-off delays.'"
}
```

UI shows this 3-part structure inline, immediately after submission.

### 7.2 Layer 2 — Post-Session Debrief Dashboard

**Reference design:** See attached dashboard mockup (dark theme, stat cards + charts).

**Chart library:** Recharts (already compatible with React/TypeScript, no extra bundle cost).

**Score range:** All skill dimension scores are stored and displayed on a **0.0–10.0 scale** across all tracks.

**Components:**

```
Stat Cards (top row, 4 cards):
  - Total Sessions Taken       + % change vs last month
  - Average Score (%)          + % change vs last month  [score/10 × 100]
  - Questions Practiced        + total count
  - Strongest Skill Dimension  + score (name + %)

Progress Overview (Recharts LineChart):
  - X axis: date (last 7 / 30 / 90 days — user-selectable)
  - Y axis: score % (0–100)
  - Line 1 (filled): Score %
  - Line 2 (dotted): Sessions taken (secondary Y)
  - Empty state: "Complete your first session to see progress"

Recommended for You (right panel):
  - AI-generated next sessions based on weak dimensions from user_progress
  - Each card: session type label, reason string, colored [Start] button
  - Empty state: "Complete a session to get recommendations"

Recent Mock Interviews (bottom left):
  - List of last 10 sessions: track icon, session name, date, duration, score %, [Review] button
  - Empty state: "No sessions yet"

Skill Breakdown (bottom right):
  - Recharts RadialBarChart (donut): overall average score, centered %
  - Recharts BarChart (horizontal): one bar per skill_dimension, score + % label
  - Color per bar: green (≥70%), amber (50–69%), red (<50%)
  - Empty state: "Practice to see your skill breakdown"
```

**DeepSeek-R1 generates:**
- Top 3 specific improvement areas (with evidence from transcript)
- Recommended next session type
- One-sentence improvement narrative per skill dimension

### 7.3 Layer 3 — Cross-Session Progress Tracking

`user_progress` table records a score per `skill_dimension` per session.

Dashboard aggregates:
- Rolling average per dimension (last 5 sessions)
- Week-over-week delta
- Trend direction (improving / stable / declining)
- Auto-recommendation: lowest-scoring dimension → suggested next session type

---

## 8. Cost Optimization

| Component | Solution | Cost |
|---|---|---|
| LLM | DeepSeek-V3 / R1 | ~$0.01/session |
| Speech-to-Text | Local whisper.cpp (runs in Electron) | Free |
| Text-to-Speech | Browser Web Speech API (SpeechSynthesis) | Free |
| Emotion detection | MediaPipe (already local) | Free |
| Avatar | Simli free tier / CSS animated fallback | Free / low |
| Question caching | Redis, key: company×track×level×stage, TTL 24h | Avoids repeat LLM calls |
| JD caching | Redis, key: SHA256(jd_text), TTL 7 days | Near-zero for repeat JDs |
| Persona caching | Redis, key: company×manager, TTL 24h | Avoids repeat LLM calls |

**Free tier realistic:** Local Whisper + browser TTS + Simli free tier + cached questions = $0.00 for repeat sessions on same company/role.

---

## 9. Updated Session Flow

```
User fills context form:
  company + role + track + level + stage + [JD] + [manager]
    ↓
JD parsed (DeepSeek-V3, cached)
    ↓
ContextPackage assembled (DB reads only)
    ↓
Questions generated (DeepSeek-V3, cached)
    ↓
Session begins:
  Avatar renders (Simli / fallback)
  Question spoken (browser TTS / local)
  User answers (text or mic → local Whisper)
  Real-time emotion feedback (MediaPipe sidebar)
  Answer graded (DeepSeek-V3)
  3-part feedback shown inline
  Next question...
    ↓
Round complete → pass/fail
    ↓
[If passed] Advance to next round OR complete session
[If failed]  Round failed screen → retry or view debrief
    ↓
Session complete → Debrief dashboard
  DeepSeek-R1 generates improvement plan
  user_progress rows written
  Community pipeline staged → Neo4j
```

---

## 10. Build Steps (Delta from v1 Plan)

### v1 Plan Status (Steps 1–24)

Steps 1–22 are built (scaffold, DB, auth, company selection, LLM orchestrator, text session, TTS, STT, avatar, emotion detection, feedback strip, debrief, multi-round pipeline, pass/fail, code editor, knowledge graph seed, persona engine, community pipeline, cross-company tracking, advanced emotion, PDF report).

Steps 23–24 (Redis/scale hardening, security audit) are **not yet built**. The new steps below include Redis as part of the caching layer (Step 37).

### New Steps (25–38)

| Step | What Gets Built | Success Gate |
|---|---|---|
| 25 | DeepSeek migration — swap `LLMOrchestrator` + `DebriefService` to DeepSeek OpenAI-compat API, remove all `anthropic` imports. `react_to_code` method continues to work unchanged (same API shape). | All existing tests pass with DeepSeek; no `anthropic` imports remain |
| 26 | `InterviewSession` schema migration — add `career_track`, `level`, `stage` columns; Alembic migration. Update `create_session` engine method + `CreateSessionRequest` schema to accept these fields. | Migration runs cleanly; existing sessions unaffected (nullable columns) |
| 27 | `knowledge_profiles` table + seed — 50 profiles covering all 10 tracks × all 5 levels at the 2 most common stages (HR Interview + Skills/Domain). Fallback: if no profile found for a combination, use the `mid-level × HR` profile for that track. | All 50 profiles queryable; fallback returns a valid profile; unit tests cover fallback path |
| 28 | Universal session entry form — replaces `CompanySelector` with full context injection UI: company, role, track picker, level picker, stage picker, JD paste field, optional manager name | User can complete the form and start a session; all fields wired to API |
| 29 | JD parser service — `JDParserService` with DeepSeek-V3; result cached by `SHA256(jd_text)` for 7 days in Redis. Redis setup (connection layer `app/core/cache.py`) included in this step. | Parser returns structured JSON for any JD; same JD never hits LLM twice |
| 30 | `ContextPackage` assembler — `ContextAssembler` service merges knowledge profile + JD parse result + Neo4j company/manager signals + user weak dimensions from `user_progress` | Assembler returns correct merged context for all 10 tracks; unit tested |
| 31 | Upgraded answer grading — `grade_answer` returns `{score, passed, what_worked, what_was_missing, stronger_version}`. Update: orchestrator prompt, `interview_engine.submit_answer` response dict, `AnswerRequest`/`GradeResponse` schemas, `interviewStore.ts` `Round` interface, `InterviewSession.tsx` feedback display | Grading response always includes all 3 feedback fields; frontend renders them; existing tests updated |
| 32 | Universal question generator — `generate_questions` uses `ContextPackage` as input; tested for all 10 tracks producing track-appropriate questions | 10 track smoke tests pass; questions contain track-specific terminology |
| 33 | `user_progress` table + `ProgressService` — writes one row per `skill_dimension` per session (score range: **0.0–10.0**, canonical for all tracks); reads rolling avg + delta | Scores written correctly after each session; rolling avg queryable per user |
| 34 | Debrief upgrade — `DebriefService` uses `deepseek-reasoner` for analysis; returns improvement plan with top 3 specific areas + recommended next session type. Persona building cached per session (1 call per session, not per round). | Plan references specific transcript moments; cached persona used for all rounds in a session |
| 35 | Progress dashboard — stat cards, Recharts line chart (axes: date × score %), Recharts donut + bar chart (skill dimensions), recommended sessions panel, recent sessions list. Dark theme matching reference design. | Dashboard renders with real data from `user_progress`; empty state handled |
| 36 | Browser TTS — replace `SpeechService.synthesize` calls in frontend with `window.speechSynthesis` (Web Speech API). OpenAI TTS remains as a premium fallback controlled by a feature flag in `.env`. | Voice works at zero cost; falls back to OpenAI TTS if flag set |
| 37 | Local Whisper integration — whisper.cpp bundled in Electron; IPC handler transcribes audio locally. OpenAI Whisper remains as fallback. | STT works offline; accuracy smoke test passes |
| 38 | Redis caching layer — cache question banks (`{company}:{track}:{level}:{stage}` TTL 24h), personas (`{company}:{manager}` TTL 24h), JD parses (`{jd_hash}` TTL 7d). Includes Redis setup from Step 29. | Cache hit confirmed on repeat company/role in integration test |
| 39 | Offer negotiation module — dedicated stage type `"offer_negotiation"` with knowledge profile; questions cover salary anchoring, package components, counter-offer scripts | Full negotiation prep session works end-to-end for all 10 tracks |

---

## 11. Success Definition

The upgraded Interview Prep module succeeds when:
1. A user can prep for any role across all 10 career tracks at any seniority level
2. Context injection produces noticeably different, company-specific questions vs generic
3. The debrief dashboard matches the reference design and shows real progress over time
4. A full session costs under $0.02 in API calls
5. Local Whisper + browser TTS make the free tier fully functional
6. The 3-part feedback system gives users actionable guidance after every single answer
