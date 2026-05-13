# Interview Prep Universal Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the tech-centric interview simulator into a universal career prep platform covering 10 career tracks, 5 seniority levels, full interview journey, DeepSeek LLM, 3-layer improvement system, and near-zero cost operation.

**Architecture:** Existing Electron + FastAPI + PostgreSQL + Neo4j stack extended with new knowledge_profiles and user_progress tables, a ContextPackage assembly pipeline, and Redis caching. LLM provider swaps from Anthropic to DeepSeek (OpenAI-compatible API). Frontend gains a universal session setup form and progress dashboard.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Neo4j, Redis, DeepSeek API (openai SDK, base_url override), Recharts, React, TypeScript, Zustand, Tailwind CSS, Vitest, pytest-asyncio

**Reference spec:** `docs/superpowers/specs/2026-05-14-interview-prep-universal-design.md`

---

## File Map

```
backend/app/services/
  llm_orchestrator.py          MODIFY  — swap Anthropic → DeepSeek, upgrade grade_answer response shape
  debrief_service.py           MODIFY  — use deepseek-reasoner, add improvement plan fields
  interview_engine.py          MODIFY  — accept career_track/level/stage, use ContextPackage
  persona_engine.py            MODIFY  — cache persona per session (not per round)
  jd_parser_service.py         CREATE  — parse JD text → structured JSON via DeepSeek
  context_assembler.py         CREATE  — merge knowledge profile + JD + graph + user history
  knowledge_service.py         CREATE  — CRUD for knowledge_profiles table
  progress_service.py          CREATE  — write/read user_progress rows

backend/app/models/pg/
  session.py                   MODIFY  — add career_track, level, stage columns to InterviewSession
  knowledge.py                 CREATE  — KnowledgeProfile ORM model
  progress.py                  CREATE  — UserProgress ORM model

backend/app/schemas/
  session.py                   MODIFY  — add career_track, level, stage to CreateSessionRequest; upgrade GradeResponse
  knowledge.py                 CREATE  — KnowledgeProfile pydantic schemas
  progress.py                  CREATE  — UserProgress pydantic schemas

backend/app/api/v1/
  sessions.py                  MODIFY  — pass new fields through to engine
  progress.py                  CREATE  — GET /progress/me endpoints

backend/app/core/
  cache.py                     MODIFY  — add cache_set/get/delete helpers (file already exists with get_redis + session state helpers)
  config.py                    MODIFY  — add deepseek_api_key (already exists), remove anthropic_api_key usage

backend/app/graph/
  knowledge_seed.py            CREATE  — seed 50 knowledge profiles on startup

backend/migrations/
  versions/xxxx_add_career_context_to_sessions.py   CREATE  via alembic
  versions/xxxx_add_knowledge_profiles.py           CREATE  via alembic
  versions/xxxx_add_user_progress.py                CREATE  via alembic

backend/tests/services/
  test_llm_orchestrator.py     MODIFY  — update mocks for DeepSeek, new grade_answer shape
  test_interview_engine.py     MODIFY  — pass career_track/level/stage
  test_jd_parser_service.py    CREATE
  test_context_assembler.py    CREATE
  test_knowledge_service.py    CREATE
  test_progress_service.py     CREATE

frontend/src/components/interview/
  SessionSetupForm.tsx          CREATE  — replaces CompanySelector, full context injection UI
  ProgressDashboard.tsx         CREATE  — stat cards + Recharts charts + recommendations

frontend/src/store/
  interviewStore.ts             MODIFY  — add career_track/level/stage, upgrade feedback type

frontend/src/hooks/
  useInterviewSession.ts        MODIFY  — pass career_track/level/stage to startSession
  useProgress.ts                CREATE  — fetch progress data for dashboard

frontend/src/pages/
  Dashboard.tsx                 MODIFY  — render ProgressDashboard when user has sessions
```

---

## Task 1: DeepSeek Migration

**Files:**
- Modify: `backend/app/services/llm_orchestrator.py`
- Modify: `backend/app/services/debrief_service.py`
- Modify: `backend/tests/services/test_llm_orchestrator.py`
- Modify: `backend/tests/services/test_interview_engine.py`

- [ ] **Step 1: Write failing test for new grade_answer shape**

Add to `backend/tests/services/test_llm_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_grade_answer_returns_three_part_feedback():
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value=json.dumps({
        "score": 7.5,
        "passed": True,
        "what_worked": "Good structure.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add: 'reduced cost by 30%.'"
    }))):
        result = await orchestrator.grade_answer(
            question="Tell me about yourself.",
            answer="I am an engineer.",
            company="Google", role="SWE", round_type="behavioral"
        )
    assert "what_worked" in result
    assert "what_was_missing" in result
    assert "stronger_version" in result
    assert "feedback" not in result
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && pytest tests/services/test_llm_orchestrator.py::test_grade_answer_returns_three_part_feedback -v
```

Expected: FAIL — `what_worked` not in result

- [ ] **Step 3: Rewrite llm_orchestrator.py**

```python
# backend/app/services/llm_orchestrator.py
import json
import re
import openai
from app.core.config import settings


class LLMOrchestrator:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self._model_fast = "deepseek-chat"       # DeepSeek-V3
        self._model_think = "deepseek-reasoner"  # DeepSeek-R1

    async def _call_llm(self, prompt: str, think: bool = False) -> str:
        model = self._model_think if think else self._model_fast
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content

    def _parse_json(self, raw: str, fallback: dict) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                return json.loads(match.group()) if match else fallback
            except (json.JSONDecodeError, AttributeError):
                return fallback

    def _parse_list(self, raw: str, fallback: list) -> list:
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\[.*\]', str(raw), re.DOTALL)
            try:
                return json.loads(match.group()) if match else fallback
            except (json.JSONDecodeError, AttributeError):
                return fallback

    async def generate_questions(
        self,
        company: str,
        role: str,
        round_type: str,
        graph_context: dict | None,
        knowledge_context: dict | None = None,
    ) -> list[str]:
        context_note = (
            f"Known interview context: {json.dumps(graph_context)}"
            if graph_context
            else "Use your general knowledge about this company's interview style."
        )
        knowledge_note = (
            f"\nRole knowledge base: {json.dumps(knowledge_context)}"
            if knowledge_context
            else ""
        )
        prompt = (
            f"You are preparing interview questions for a {round_type} interview at {company} "
            f"for a {role} position.\n{context_note}{knowledge_note}\n\n"
            "Generate 5 interview questions appropriate for this round and seniority level. "
            'Return only a JSON array of question strings.\nExample: ["Question 1?", "Question 2?"]'
        )
        raw = await self._call_llm(prompt)
        return self._parse_list(raw, ["Tell me about yourself."])

    async def grade_answer(
        self,
        question: str,
        answer: str,
        company: str,
        role: str,
        round_type: str,
    ) -> dict:
        prompt = (
            f"You are a {round_type} interviewer at {company} evaluating a candidate for {role}.\n\n"
            f"Question: {question}\nCandidate answer: {answer}\n\n"
            "Grade this answer on a scale of 1-10. A score >= 6 means passed.\n"
            "Return JSON only — no other text:\n"
            '{"score": 7.5, "passed": true, "what_worked": "One sentence.", '
            '"what_was_missing": "One sentence.", "stronger_version": "One sentence showing improvement."}'
        )
        raw = await self._call_llm(prompt)
        return self._parse_json(raw, {
            "score": 5.0, "passed": False,
            "what_worked": "", "what_was_missing": "Could not grade answer.",
            "stronger_version": ""
        })

    async def build_persona(self, company: str, role: str, manager_context: dict | None) -> str:
        context = json.dumps(manager_context) if manager_context else "No prior data available."
        prompt = (
            f"Build a concise interviewer persona for a hiring manager at {company} for the {role} role.\n"
            f"Known manager data: {context}\n"
            "Return a 2-3 sentence personality description the AI avatar should embody."
        )
        return await self._call_llm(prompt)

    async def react_to_code(self, code_snapshot: str, question: str, company: str) -> str:
        prompt = (
            f"You are a technical interviewer at {company}.\n"
            f"The candidate is solving: {question}\n\nTheir current code:\n{code_snapshot}\n\n"
            "Give a brief (1-2 sentence) natural spoken reaction as an interviewer watching them code. "
            "Don't give away the answer. Be encouraging but probe for edge cases if appropriate."
        )
        return await self._call_llm(prompt)
```

- [ ] **Step 4: Update debrief_service.py to use DeepSeek**

Replace the `anthropic` import and client in `backend/app/services/debrief_service.py`:

```python
# Remove:
import anthropic
# ...
self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# Replace _call_claude with:
import openai

# In __init__:
self._client = openai.AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url="https://api.deepseek.com",
)

# Replace _call_claude method:
async def _call_llm(self, prompt: str) -> dict:
    response = await self._client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(m.group()) if m else {
            "overall_score": 5.0, "strengths": [], "improvements": [],
            "recommendation": raw[:200]
        }
```

Also rename all `_call_claude(` calls in debrief_service.py to `_call_llm(`.

- [ ] **Step 5: Update test mocks to use _call_llm**

In `backend/tests/services/test_llm_orchestrator.py`, replace all `_call_claude` with `_call_llm`.
In `backend/tests/services/test_interview_engine.py`, no changes needed (mocks the orchestrator directly).

- [ ] **Step 6: Run all orchestrator tests**

```bash
cd backend && pytest tests/services/test_llm_orchestrator.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/llm_orchestrator.py backend/app/services/debrief_service.py backend/tests/services/test_llm_orchestrator.py
git commit -m "feat(step-25): migrate LLM provider from Claude to DeepSeek-V3/R1, upgrade grade_answer to 3-part feedback"
```

---

## Task 2: Propagate 3-Part Feedback Through Stack

**Files:**
- Modify: `backend/app/schemas/session.py`
- Modify: `backend/app/services/interview_engine.py`
- Modify: `backend/tests/services/test_interview_engine.py`
- Modify: `frontend/src/store/interviewStore.ts`
- Modify: `frontend/src/components/interview/InterviewSession.tsx`
- Modify: `frontend/src/hooks/useInterviewSession.ts`

- [ ] **Step 1: Update GradeResponse schema**

In `backend/app/schemas/session.py`, replace `GradeResponse`:

```python
class GradeResponse(BaseModel):
    score: float
    passed: bool
    what_worked: str
    what_was_missing: str
    stronger_version: str
    round_complete: bool = False
    round_passed: bool | None = None
```

- [ ] **Step 2: Update interview_engine.submit_answer return dict**

In `backend/app/services/interview_engine.py`, replace the final `return` in `submit_answer`:

```python
return {
    "score": grade["score"],
    "passed": grade["passed"],
    "what_worked": grade.get("what_worked", ""),
    "what_was_missing": grade.get("what_was_missing", ""),
    "stronger_version": grade.get("stronger_version", ""),
    "round_complete": round_complete,
    "round_passed": round_passed,
}
```

- [ ] **Step 3: Update test_interview_engine.py mock**

In `backend/tests/services/test_interview_engine.py`, update the `grade_answer` mock return value:

```python
mock_orchestrator.grade_answer.return_value = {
    "score": 8.0, "passed": True,
    "what_worked": "Good structure.",
    "what_was_missing": "No metrics.",
    "stronger_version": "Add quantified result."
}
```

Add assertion:
```python
assert result["what_worked"] == "Good structure."
```

- [ ] **Step 4: Run backend tests**

```bash
cd backend && pytest tests/services/test_interview_engine.py -v
```

Expected: PASS

- [ ] **Step 5: Update frontend interviewStore.ts**

In `frontend/src/store/interviewStore.ts`, update the `Round` interface:

```typescript
interface FeedbackResult {
  what_worked: string
  what_was_missing: string
  stronger_version: string
  passed: boolean
}

interface Round {
  id: string
  type: string
  questions: string[]
  currentQuestionIndex: number
  passed?: boolean
  feedbackResult?: FeedbackResult
}
```

Update `setRoundResult` action signature:

```typescript
setRoundResult: (passed: boolean, feedbackResult: FeedbackResult) =>
  set((s) => (s.currentRound ? { currentRound: { ...s.currentRound, passed, feedbackResult } } : s)),
```

- [ ] **Step 6: Update InterviewSession.tsx feedback display**

In `frontend/src/components/interview/InterviewSession.tsx`:

Replace the `feedback` state type:

```typescript
const [feedback, setFeedback] = useState<{
  what_worked: string
  what_was_missing: string
  stronger_version: string
  passed: boolean
  roundComplete: boolean
  roundPassed: boolean | null
} | null>(null)
```

In `handleSubmit`, replace the feedback setter:

```typescript
setFeedback({
  what_worked: result.what_worked,
  what_was_missing: result.what_was_missing,
  stronger_version: result.stronger_version,
  passed: result.passed,
  roundComplete: result.round_complete ?? false,
  roundPassed: result.round_passed ?? null,
})
setRoundResult(result.passed, {
  what_worked: result.what_worked,
  what_was_missing: result.what_was_missing,
  stronger_version: result.stronger_version,
  passed: result.passed,
})
```

Replace feedback display block (the green/red box) with:

```tsx
{feedback && (
  <div className={`rounded-xl p-4 text-sm leading-relaxed space-y-2 ${
    feedback.passed
      ? 'bg-green-950 border border-green-700'
      : 'bg-red-950 border border-red-700'
  }`}>
    {feedback.what_worked && (
      <p className="text-green-300">
        <span className="font-semibold">✓ Worked: </span>{feedback.what_worked}
      </p>
    )}
    {feedback.what_was_missing && (
      <p className="text-yellow-300">
        <span className="font-semibold">△ Missing: </span>{feedback.what_was_missing}
      </p>
    )}
    {feedback.stronger_version && (
      <p className="text-blue-300">
        <span className="font-semibold">→ Stronger: </span>{feedback.stronger_version}
      </p>
    )}
  </div>
)}
```

Also remove the call to `speak(result.feedback)` and replace with `speak(result.what_worked || '')`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/session.py backend/app/services/interview_engine.py backend/tests/ frontend/src/store/interviewStore.ts frontend/src/components/interview/InterviewSession.tsx
git commit -m "feat(step-31): 3-part feedback — what_worked/missing/stronger_version throughout stack"
```

---

## Task 3: DB Schema — Career Context + Knowledge Profiles + User Progress

**Files:**
- Modify: `backend/app/models/pg/session.py`
- Create: `backend/app/models/pg/knowledge.py`
- Create: `backend/app/models/pg/progress.py`
- Create Alembic migrations (3)

- [ ] **Step 1: Add columns to InterviewSession model**

In `backend/app/models/pg/session.py`, add to `InterviewSession`:

```python
career_track: Mapped[str | None] = mapped_column(String(100), nullable=True)
level: Mapped[str | None] = mapped_column(String(50), nullable=True)
interview_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
jd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

- [ ] **Step 2: Create knowledge.py model**

```python
# backend/app/models/pg/knowledge.py
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class KnowledgeProfile(Base):
    __tablename__ = "knowledge_profiles"
    __table_args__ = (UniqueConstraint("track", "level", "stage", name="uq_knowledge_profile"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    track: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
```

- [ ] **Step 3: Create progress.py model**

```python
# backend/app/models/pg/progress.py
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    career_track: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0–10.0
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

- [ ] **Step 4: Import new models in Alembic env.py**

In `backend/migrations/env.py`, add:

```python
from app.models.pg.knowledge import KnowledgeProfile
from app.models.pg.progress import UserProgress
```

- [ ] **Step 5: Generate and run migrations**

```bash
cd backend
alembic revision --autogenerate -m "add career context columns to sessions"
alembic revision --autogenerate -m "add knowledge profiles table"
alembic revision --autogenerate -m "add user progress table"
alembic upgrade head
```

- [ ] **Step 6: Write migration smoke test**

Add to `backend/tests/test_db_connections.py`:

```python
@pytest.mark.asyncio
async def test_new_tables_exist():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        tables = {row[0] for row in result}
    assert "knowledge_profiles" in tables
    assert "user_progress" in tables
    await engine.dispose()
```

- [ ] **Step 7: Run**

```bash
pytest tests/test_db_connections.py -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/pg/ backend/migrations/ backend/tests/test_db_connections.py
git commit -m "feat(step-26): DB schema — career_track/level/stage on sessions, knowledge_profiles, user_progress tables"
```

---

## Task 4: Redis Cache Layer

**Files:**
- Modify: `backend/app/core/cache.py` (already exists — add generic helpers without touching existing `get_redis`/`set_session_state`)
- Create: `backend/tests/test_cache.py`

> **Note:** `cache.py` already exists with `get_redis()`, `set_session_state()`, `get_session_state()`, `delete_session_state()`. Do NOT overwrite — only append the new generic helpers below.

- [ ] **Step 1: Write failing cache test**

```python
# backend/tests/test_cache.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_set_and_get_returns_value():
    with patch("app.core.cache.get_redis") as mock_factory:
        mock_r = AsyncMock()
        mock_r.setex = AsyncMock()
        mock_r.get = AsyncMock(return_value='{"key": "value"}')
        mock_factory.return_value = mock_r

        from app.core.cache import cache_set, cache_get
        await cache_set("test:key", {"key": "value"}, ttl=60)
        result = await cache_get("test:key")
        assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_get_missing_key_returns_none():
    with patch("app.core.cache.get_redis") as mock_factory:
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_factory.return_value = mock_r

        from app.core.cache import cache_get
        result = await cache_get("missing:key")
        assert result is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && pytest tests/test_cache.py -v
```

Expected: FAIL — `cache_set` not defined

- [ ] **Step 3: Append helpers to existing cache.py**

Open `backend/app/core/cache.py` and APPEND these functions at the bottom (do not remove any existing code):

```python
# ── Generic key/value cache helpers (used by JD parser, knowledge service, etc.) ──

async def cache_set(key: str, value: dict | list, ttl: int = 86400) -> None:
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> dict | list | None:
    r = await get_redis()
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cache.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/cache.py backend/tests/test_cache.py
git commit -m "feat(step-29a): Redis cache layer — add cache_set/get/delete generic helpers to existing cache.py"
```

---

## Task 5: Knowledge Service + Seed

**Files:**
- Create: `backend/app/services/knowledge_service.py`
- Create: `backend/app/graph/knowledge_seed.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/services/test_knowledge_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/test_knowledge_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.knowledge_service import KnowledgeService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_profile_returns_profile(mock_db):
    fake_profile = MagicMock()
    fake_profile.profile = {
        "core_competencies": ["coding", "system design"],
        "skill_dimensions": ["domain_knowledge", "communication_clarity"],
    }
    mock_db.execute.return_value.scalar_one_or_none.return_value = fake_profile
    svc = KnowledgeService(db=mock_db)
    result = await svc.get_profile("technology", "mid_level", "skills_domain")
    assert result["core_competencies"] == ["coding", "system design"]


@pytest.mark.asyncio
async def test_get_profile_returns_fallback_when_missing(mock_db):
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    # second call for fallback (hr_interview)
    fake_fallback = MagicMock()
    fake_fallback.profile = {"core_competencies": ["communication"], "skill_dimensions": ["communication_clarity"]}
    mock_db.execute.return_value.scalar_one_or_none.side_effect = [None, fake_fallback]
    svc = KnowledgeService(db=mock_db)
    result = await svc.get_profile("technology", "mid_level", "panel_interview")
    assert result is not None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && pytest tests/services/test_knowledge_service.py -v
```

- [ ] **Step 3: Create knowledge_service.py**

```python
# backend/app/services/knowledge_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.knowledge import KnowledgeProfile


class KnowledgeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, track: str, level: str, stage: str) -> dict | None:
        result = await self.db.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.track == track,
                KnowledgeProfile.level == level,
                KnowledgeProfile.stage == stage,
            )
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile.profile

        # Fallback: same track + level, hr_interview stage
        fallback = await self.db.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.track == track,
                KnowledgeProfile.level == level,
                KnowledgeProfile.stage == "hr_interview",
            )
        )
        fb = fallback.scalar_one_or_none()
        return fb.profile if fb else None
```

- [ ] **Step 4: Create knowledge_seed.py**

```python
# backend/app/graph/knowledge_seed.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.knowledge import KnowledgeProfile

# ── Seed data: 10 tracks × 5 levels, stage = hr_interview ────────────────────
# Each profile: core_competencies, question_archetypes, evaluation_rubrics,
#               answer_frameworks, common_pitfalls, red_flags, skill_dimensions

TRACKS = [
    "technology", "finance_fintech", "healthcare", "business_consulting",
    "sales_marketing", "design_creative", "legal_compliance",
    "hr_people", "education_training", "operations_supply_chain",
]

LEVELS = ["entry_junior", "mid_level", "senior", "lead_manager", "director_vp_csuite"]

LEVEL_LABELS = {
    "entry_junior": "entry-level",
    "mid_level": "mid-level",
    "senior": "senior",
    "lead_manager": "manager/lead",
    "director_vp_csuite": "executive/C-suite",
}

TRACK_DATA = {
    "technology": {
        "label": "technology",
        "competencies": {
            "entry_junior": ["coding fundamentals", "debugging", "version control", "basic algorithms", "teamwork"],
            "mid_level": ["system design basics", "code quality", "testing", "API design", "problem solving"],
            "senior": ["architecture decisions", "performance optimization", "mentoring", "cross-team collaboration", "technical strategy"],
            "lead_manager": ["engineering management", "roadmap planning", "hiring", "stakeholder communication", "delivery"],
            "director_vp_csuite": ["technology vision", "organizational design", "budget ownership", "board communication", "competitive strategy"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "problem_solving", "leadership_narrative", "quantified_impact"],
    },
    "finance_fintech": {
        "label": "finance/fintech",
        "competencies": {
            "entry_junior": ["financial modeling basics", "Excel/spreadsheets", "data analysis", "attention to detail", "regulatory awareness"],
            "mid_level": ["financial analysis", "valuation", "risk assessment", "client communication", "reporting"],
            "senior": ["deal structuring", "portfolio management", "team leadership", "regulatory compliance", "P&L ownership"],
            "lead_manager": ["team building", "client relationships", "budget management", "strategy execution", "risk governance"],
            "director_vp_csuite": ["capital allocation", "M&A strategy", "board reporting", "regulatory leadership", "organizational design"],
        },
        "frameworks": ["STAR", "SOAR", "MECE", "Pyramid Principle"],
        "dimensions": ["domain_knowledge", "quantified_impact", "executive_presence", "leadership_narrative", "culture_alignment"],
    },
    "healthcare": {
        "label": "healthcare",
        "competencies": {
            "entry_junior": ["patient care basics", "clinical protocols", "documentation", "teamwork", "empathy"],
            "mid_level": ["clinical expertise", "patient outcomes", "interdisciplinary collaboration", "quality improvement", "evidence-based practice"],
            "senior": ["clinical leadership", "mentoring", "process improvement", "compliance", "complex case management"],
            "lead_manager": ["department management", "staff development", "budget oversight", "regulatory compliance", "strategic planning"],
            "director_vp_csuite": ["healthcare strategy", "population health", "organizational leadership", "board relations", "policy development"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment", "quantified_impact"],
    },
    "business_consulting": {
        "label": "business/consulting",
        "competencies": {
            "entry_junior": ["structured thinking", "data analysis", "presentation skills", "client interaction", "research"],
            "mid_level": ["project management", "client management", "hypothesis-driven analysis", "team coordination", "deliverable quality"],
            "senior": ["engagement leadership", "business development", "complex problem solving", "senior client relationships", "team development"],
            "lead_manager": ["practice leadership", "P&L management", "talent development", "key account ownership", "thought leadership"],
            "director_vp_csuite": ["firm strategy", "market positioning", "C-suite advisory", "organizational leadership", "business development"],
        },
        "frameworks": ["MECE", "Pyramid Principle", "STAR", "Case framework"],
        "dimensions": ["domain_knowledge", "problem_solving", "communication_clarity", "executive_presence", "quantified_impact"],
    },
    "sales_marketing": {
        "label": "sales/marketing",
        "competencies": {
            "entry_junior": ["product knowledge", "prospecting basics", "CRM usage", "communication", "resilience"],
            "mid_level": ["pipeline management", "negotiation", "account management", "data-driven marketing", "customer success"],
            "senior": ["revenue ownership", "team enablement", "strategic accounts", "go-to-market strategy", "forecasting"],
            "lead_manager": ["sales team leadership", "quota management", "hiring", "marketing strategy", "budget ownership"],
            "director_vp_csuite": ["revenue strategy", "market expansion", "brand leadership", "board reporting", "competitive positioning"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["quantified_impact", "domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment"],
    },
    "design_creative": {
        "label": "design/creative",
        "competencies": {
            "entry_junior": ["design tools", "visual communication", "user empathy", "iteration", "feedback receptiveness"],
            "mid_level": ["UX research", "interaction design", "design systems", "stakeholder communication", "data-informed design"],
            "senior": ["design strategy", "cross-functional leadership", "design ops", "mentoring", "systems thinking"],
            "lead_manager": ["team leadership", "design culture", "roadmap influence", "exec communication", "hiring"],
            "director_vp_csuite": ["design vision", "brand strategy", "organizational influence", "C-suite partnership", "design ROI"],
        },
        "frameworks": ["STAR", "Portfolio review"],
        "dimensions": ["domain_knowledge", "communication_clarity", "problem_solving", "leadership_narrative", "culture_alignment"],
    },
    "legal_compliance": {
        "label": "legal/compliance",
        "competencies": {
            "entry_junior": ["legal research", "contract basics", "attention to detail", "writing", "regulatory awareness"],
            "mid_level": ["contract negotiation", "risk analysis", "regulatory compliance", "client advisory", "litigation support"],
            "senior": ["complex transactions", "regulatory strategy", "team leadership", "senior client relationships", "risk management"],
            "lead_manager": ["practice management", "business development", "team development", "client retention", "compliance program ownership"],
            "director_vp_csuite": ["legal strategy", "board advisory", "M&A oversight", "regulatory leadership", "organizational governance"],
        },
        "frameworks": ["STAR", "IRAC"],
        "dimensions": ["domain_knowledge", "communication_clarity", "problem_solving", "executive_presence", "culture_alignment"],
    },
    "hr_people": {
        "label": "HR/people",
        "competencies": {
            "entry_junior": ["recruiting basics", "HRIS tools", "employee onboarding", "communication", "confidentiality"],
            "mid_level": ["talent acquisition", "employee relations", "performance management", "HR analytics", "L&D programs"],
            "senior": ["HR strategy", "organizational development", "change management", "total rewards", "culture programs"],
            "lead_manager": ["HR business partnership", "team leadership", "workforce planning", "senior stakeholder management", "DEI programs"],
            "director_vp_csuite": ["people strategy", "C-suite partnership", "organizational design", "culture transformation", "board reporting"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment", "quantified_impact"],
    },
    "education_training": {
        "label": "education/training",
        "competencies": {
            "entry_junior": ["lesson planning", "classroom management", "communication", "student engagement", "assessment design"],
            "mid_level": ["curriculum development", "differentiated instruction", "student outcomes", "parent communication", "professional development"],
            "senior": ["instructional leadership", "curriculum design", "teacher mentoring", "program evaluation", "stakeholder engagement"],
            "lead_manager": ["school/program leadership", "staff development", "budget management", "community relations", "strategic planning"],
            "director_vp_csuite": ["educational strategy", "policy development", "organizational leadership", "board relations", "system-wide improvement"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment", "quantified_impact"],
    },
    "operations_supply_chain": {
        "label": "operations/supply chain",
        "competencies": {
            "entry_junior": ["process documentation", "data entry", "coordination", "problem identification", "tool proficiency"],
            "mid_level": ["process optimization", "vendor management", "project coordination", "data analysis", "cross-functional collaboration"],
            "senior": ["operations strategy", "supply chain design", "team leadership", "cost optimization", "risk management"],
            "lead_manager": ["operations management", "team development", "P&L ownership", "vendor strategy", "capacity planning"],
            "director_vp_csuite": ["supply chain strategy", "global operations", "organizational leadership", "board reporting", "digital transformation"],
        },
        "frameworks": ["STAR", "SOAR", "DMAIC"],
        "dimensions": ["domain_knowledge", "quantified_impact", "problem_solving", "leadership_narrative", "communication_clarity"],
    },
}

RUBRICS = {
    "excellent": "Quantified impact, structured answer, clear ownership, level-appropriate framing",
    "good": "Structured answer, relevant experience, some specifics, demonstrates growth",
    "needs_work": "Vague, limited specifics, missing ownership or metrics",
    "poor": "No structure, irrelevant, bad-mouths past employer, no self-awareness",
}

COMMON_PITFALLS = [
    "Answering at a lower seniority level than expected",
    "Not quantifying outcomes or impact",
    "Forgetting to ask questions at the end",
    "Over-explaining without landing a clear point",
    "Bad-mouthing a previous employer or colleague",
]

RED_FLAGS = [
    "Cannot describe impact of their work in numbers",
    "Blames others exclusively for past failures",
    "No questions for the interviewer",
    "Inconsistent career narrative",
    "Dismissive of the company's challenges",
]


def _build_profile(track: str, level: str, stage: str = "hr_interview") -> dict:
    t = TRACK_DATA[track]
    label = t["label"]
    level_label = LEVEL_LABELS[level]
    competencies = t["competencies"][level]
    if stage == "skills_domain":
        archetype_type = "technical"
        example_prefix = f"Walk me through how you would approach {competencies[0]} at the {level_label} level"
        weight_behavioral = 0.3
        weight_technical = 0.5
        weight_situational = 0.2
    else:
        archetype_type = "behavioral"
        example_prefix = f"Tell me about a time you demonstrated {competencies[0]} in a {label} role"
        weight_behavioral = 0.4
        weight_technical = 0.0
        weight_situational = 0.3
    question_archetypes = [
        {
            "type": archetype_type,
            "framework": t["frameworks"][0],
            "weight": weight_behavioral if stage == "hr_interview" else weight_technical,
            "example": f"{example_prefix}.",
        },
        {
            "type": "motivational",
            "framework": "open",
            "weight": 0.3 if stage == "hr_interview" else weight_situational,
            "example": f"Why do you want to be a {level_label} in {label}?",
        },
        {
            "type": "situational",
            "framework": t["frameworks"][1] if len(t["frameworks"]) > 1 else t["frameworks"][0],
            "weight": weight_situational,
            "example": f"How would you approach a conflict on your team as a {level_label}?",
        },
    ]
    return {
        "track": track,
        "level": level,
        "stage": stage,
        "core_competencies": competencies,
        "question_archetypes": question_archetypes,
        "evaluation_rubrics": RUBRICS,
        "answer_frameworks": t["frameworks"],
        "common_pitfalls": COMMON_PITFALLS,
        "red_flags": RED_FLAGS,
        "skill_dimensions": t["dimensions"],
    }


async def _seed_stage(db: AsyncSession, stage: str) -> None:
    for track in TRACKS:
        for level in LEVELS:
            existing = await db.execute(
                select(KnowledgeProfile).where(
                    KnowledgeProfile.track == track,
                    KnowledgeProfile.level == level,
                    KnowledgeProfile.stage == stage,
                )
            )
            if existing.scalar_one_or_none():
                continue
            profile_data = _build_profile(track, level, stage)
            db.add(KnowledgeProfile(
                id=str(uuid.uuid4()),
                track=track, level=level, stage=stage, profile=profile_data,
            ))
    await db.commit()


async def seed_knowledge_profiles(db: AsyncSession) -> None:
    await _seed_stage(db, "hr_interview")   # 50 profiles
    await _seed_stage(db, "skills_domain")  # 50 profiles
```

- [ ] **Step 5: Call seed on startup in main.py**

In `backend/app/main.py`, update the lifespan to call `seed_knowledge_profiles`:

```python
from app.graph.knowledge_seed import seed_knowledge_profiles
from app.core.database import AsyncSessionLocal

@asynccontextmanager
async def lifespan(app):
    await run_seed()  # existing Neo4j seed
    async with AsyncSessionLocal() as db:
        await seed_knowledge_profiles(db)
    yield
```

- [ ] **Step 6: Run knowledge service tests**

```bash
cd backend && pytest tests/services/test_knowledge_service.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/knowledge_service.py backend/app/graph/knowledge_seed.py backend/app/main.py backend/tests/services/test_knowledge_service.py
git commit -m "feat(step-27): knowledge profiles — 100 seeded profiles (10 tracks × 5 levels × 2 stages), fallback logic"
```

---

## Task 6: JD Parser Service

**Files:**
- Create: `backend/app/services/jd_parser_service.py`
- Create: `backend/tests/services/test_jd_parser_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/test_jd_parser_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.jd_parser_service import JDParserService

SAMPLE_JD = """
We are looking for a Senior Software Engineer to join our platform team.
Required: 5+ years Python, distributed systems experience, strong communication skills.
Nice to have: Kubernetes, Rust. Fast-paced environment, high ownership expected.
"""

@pytest.mark.asyncio
async def test_parse_returns_structured_output():
    svc = JDParserService()
    mock_response = {
        "required_skills": ["Python", "distributed systems"],
        "preferred_skills": ["Kubernetes", "Rust"],
        "culture_signals": ["fast-paced", "high ownership"],
        "red_flags_to_avoid": [],
        "implied_seniority": "senior",
        "key_responsibilities": ["platform engineering"],
    }
    with patch.object(svc, '_call_llm', new=AsyncMock(return_value=str(mock_response))):
        result = await svc.parse(SAMPLE_JD)
    assert "required_skills" in result
    assert "culture_signals" in result

@pytest.mark.asyncio
async def test_parse_returns_empty_dict_for_blank_jd():
    svc = JDParserService()
    result = await svc.parse("")
    assert result == {}
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && pytest tests/services/test_jd_parser_service.py -v
```

- [ ] **Step 3: Create jd_parser_service.py**

```python
# backend/app/services/jd_parser_service.py
import hashlib
import json
import re
import openai
from app.core.config import settings
from app.core.cache import cache_set, cache_get

_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


class JDParserService:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )

    async def _call_llm(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        return response.choices[0].message.content

    async def parse(self, jd_text: str) -> dict:
        if not jd_text or not jd_text.strip():
            return {}

        jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()
        cache_key = f"jd:{jd_hash}"

        cached = await cache_get(cache_key)
        if cached:
            return cached

        prompt = (
            "Extract structured information from this job description.\n\n"
            f"JD:\n{jd_text}\n\n"
            "Return JSON only:\n"
            '{"required_skills": [], "preferred_skills": [], "culture_signals": [], '
            '"red_flags_to_avoid": [], "implied_seniority": "", "key_responsibilities": []}'
        )
        raw = await self._call_llm(prompt)
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                result = json.loads(match.group()) if match else {}
            except (json.JSONDecodeError, AttributeError):
                result = {}

        if result:
            await cache_set(cache_key, result, ttl=_CACHE_TTL)
        return result
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_jd_parser_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/jd_parser_service.py backend/tests/services/test_jd_parser_service.py
git commit -m "feat(step-29b): JD parser service — DeepSeek-V3, SHA256 cache, structured extraction"
```

---

## Task 8: ContextPackage Assembler

> ⚠️ **PREREQUISITE: Complete Task 7 (Progress Service) before this task.** `context_assembler.py` imports `ProgressService` at the top level — it will fail to import if `progress_service.py` does not exist yet. Even though Task 7 appears after this section in the document, implement it first.

**Files:**
- Create: `backend/app/services/context_assembler.py`
- Create: `backend/tests/services/test_context_assembler.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/test_context_assembler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.context_assembler import ContextAssembler


@pytest.mark.asyncio
async def test_assemble_returns_merged_context():
    mock_db = AsyncMock()

    # KnowledgeService returns a profile
    with patch("app.services.context_assembler.KnowledgeService") as MockKS, \
         patch("app.services.context_assembler.JDParserService") as MockJD, \
         patch("app.services.context_assembler.get_round_context", new=AsyncMock(return_value={})), \
         patch("app.services.context_assembler.ProgressService") as MockPS:

        MockKS.return_value.get_profile = AsyncMock(return_value={
            "core_competencies": ["Python", "system design"],
            "skill_dimensions": ["domain_knowledge"],
        })
        MockJD.return_value.parse = AsyncMock(return_value={
            "required_skills": ["Python"],
            "culture_signals": ["fast-paced"],
        })
        MockPS.return_value.get_weak_dimensions = AsyncMock(return_value=["communication_clarity"])

        assembler = ContextAssembler(db=mock_db)
        ctx = await assembler.assemble(
            user_id="u1", company="Stripe", role="SWE",
            career_track="technology", level="senior",
            interview_stage="hr_interview", jd_text="Python engineer role",
        )

    assert ctx["knowledge_profile"]["core_competencies"] == ["Python", "system design"]
    assert ctx["jd_analysis"]["required_skills"] == ["Python"]
    assert "communication_clarity" in ctx["user_weak_dimensions"]


@pytest.mark.asyncio
async def test_assemble_works_without_jd():
    mock_db = AsyncMock()
    with patch("app.services.context_assembler.KnowledgeService") as MockKS, \
         patch("app.services.context_assembler.JDParserService") as MockJD, \
         patch("app.services.context_assembler.get_round_context", new=AsyncMock(return_value={})), \
         patch("app.services.context_assembler.ProgressService") as MockPS:

        MockKS.return_value.get_profile = AsyncMock(return_value={"core_competencies": []})
        MockJD.return_value.parse = AsyncMock(return_value={})
        MockPS.return_value.get_weak_dimensions = AsyncMock(return_value=[])

        assembler = ContextAssembler(db=mock_db)
        ctx = await assembler.assemble(
            user_id="u1", company="Google", role="PM",
            career_track="technology", level="mid_level",
            interview_stage="hr_interview", jd_text=None,
        )

    assert ctx["jd_analysis"] == {}
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && pytest tests/services/test_context_assembler.py -v
```

- [ ] **Step 3: Create context_assembler.py**

```python
# backend/app/services/context_assembler.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.knowledge_service import KnowledgeService
from app.services.jd_parser_service import JDParserService
from app.services.progress_service import ProgressService
from app.graph.round_queries import get_round_context


class ContextAssembler:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble(
        self,
        user_id: str,
        company: str,
        role: str,
        career_track: str,
        level: str,
        interview_stage: str,
        jd_text: str | None = None,
        manager_name: str | None = None,
    ) -> dict:
        knowledge_svc = KnowledgeService(db=self.db)
        jd_svc = JDParserService()
        progress_svc = ProgressService(db=self.db)

        knowledge_profile, jd_analysis, graph_context, weak_dimensions = await _gather(
            knowledge_svc, jd_svc, progress_svc,
            career_track, level, interview_stage,
            company, user_id, jd_text,
        )

        return {
            "company": company,
            "role": role,
            "career_track": career_track,
            "level": level,
            "interview_stage": interview_stage,
            "knowledge_profile": knowledge_profile or {},
            "jd_analysis": jd_analysis,
            "graph_context": graph_context,
            "user_weak_dimensions": weak_dimensions,
            "manager_name": manager_name,
        }


async def _gather(knowledge_svc, jd_svc, progress_svc,
                  career_track, level, interview_stage,
                  company, user_id, jd_text):
    import asyncio
    results = await asyncio.gather(
        knowledge_svc.get_profile(career_track, level, interview_stage),
        jd_svc.parse(jd_text) if jd_text else _empty(),
        get_round_context(company, interview_stage),
        progress_svc.get_weak_dimensions(user_id, career_track),
    )
    return results


async def _empty():
    return {}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/services/test_context_assembler.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/context_assembler.py backend/tests/services/test_context_assembler.py
git commit -m "feat(step-30): ContextPackage assembler — merges knowledge profile, JD, graph, user history"
```

---

## Task 7: Progress Service

> ✅ **Implement this BEFORE Task 8 (ContextPackage Assembler).** Task 8 imports `ProgressService` at module level, so this file must exist first.

**Files:**
- Create: `backend/app/services/progress_service.py`
- Create: `backend/app/api/v1/progress.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/services/test_progress_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/test_progress_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.progress_service import ProgressService


@pytest.mark.asyncio
async def test_write_scores_adds_rows():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    svc = ProgressService(db=mock_db)
    await svc.write_scores(
        user_id="u1", session_id="s1",
        career_track="technology", level="mid_level", stage="hr_interview",
        scores={"domain_knowledge": 8.0, "communication_clarity": 6.5},
    )
    assert mock_db.add.call_count == 2
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_weak_dimensions_returns_lowest():
    mock_db = AsyncMock()
    rows = [
        MagicMock(skill_dimension="domain_knowledge", score=8.0),
        MagicMock(skill_dimension="communication_clarity", score=4.0),
        MagicMock(skill_dimension="executive_presence", score=3.5),
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = rows
    svc = ProgressService(db=mock_db)
    weak = await svc.get_weak_dimensions("u1", "technology", n=2)
    assert "executive_presence" in weak
    assert "communication_clarity" in weak
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && pytest tests/services/test_progress_service.py -v
```

- [ ] **Step 3: Create progress_service.py**

```python
# backend/app/services/progress_service.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.progress import UserProgress


class ProgressService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_scores(
        self,
        user_id: str,
        session_id: str,
        career_track: str,
        level: str,
        stage: str,
        scores: dict[str, float],
    ) -> None:
        for dimension, score in scores.items():
            row = UserProgress(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                career_track=career_track,
                level=level,
                stage=stage,
                skill_dimension=dimension,
                score=max(0.0, min(10.0, score)),
            )
            self.db.add(row)
        await self.db.commit()

    async def get_weak_dimensions(
        self, user_id: str, career_track: str, n: int = 3
    ) -> list[str]:
        result = await self.db.execute(
            select(UserProgress)
            .where(UserProgress.user_id == user_id, UserProgress.career_track == career_track)
            .order_by(UserProgress.recorded_at.desc())
            .limit(50)
        )
        rows = result.scalars().all()
        if not rows:
            return []
        avgs: dict[str, list[float]] = {}
        for row in rows:
            avgs.setdefault(row.skill_dimension, []).append(row.score)
        avg_scores = {dim: sum(scores) / len(scores) for dim, scores in avgs.items()}
        return sorted(avg_scores, key=lambda d: avg_scores[d])[:n]

    async def get_summary(self, user_id: str) -> dict:
        result = await self.db.execute(
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .order_by(UserProgress.recorded_at.desc())
            .limit(200)
        )
        rows = result.scalars().all()
        if not rows:
            return {"dimensions": {}, "total_sessions": 0, "average_score": 0.0}

        dim_scores: dict[str, list[float]] = {}
        session_ids = set()
        for row in rows:
            dim_scores.setdefault(row.skill_dimension, []).append(row.score)
            session_ids.add(row.session_id)

        dimensions = {
            dim: round(sum(scores) / len(scores), 2)
            for dim, scores in dim_scores.items()
        }
        all_scores = [s for scores in dim_scores.values() for s in scores]
        return {
            "dimensions": dimensions,
            "total_sessions": len(session_ids),
            "average_score": round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0,
        }
```

- [ ] **Step 4: Create progress API**

```python
# backend/app/api/v1/progress.py
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress", tags=["progress"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/me")
async def get_my_progress(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    svc = ProgressService(db=db)
    summary = await svc.get_summary(user_id=user_id)
    return {"data": summary, "error": None}
```

Register in `backend/app/main.py`:

```python
from app.api.v1.progress import router as progress_router
app.include_router(progress_router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/services/test_progress_service.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/progress_service.py backend/app/api/v1/progress.py backend/app/main.py backend/tests/services/test_progress_service.py
git commit -m "feat(step-33a): progress service — write skill dimension scores, weak area detection, summary API"
```

---

## Task 9: Wire Career Context Through Session Creation

**Files:**
- Modify: `backend/app/schemas/session.py`
- Modify: `backend/app/services/interview_engine.py`
- Modify: `backend/app/api/v1/sessions.py`
- Modify: `backend/tests/services/test_interview_engine.py`

- [ ] **Step 1: Update CreateSessionRequest schema**

In `backend/app/schemas/session.py`:

```python
class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round_types: list[str]
    career_track: str = "technology"
    level: str = "mid_level"
    interview_stage: str = "hr_interview"
    jd_text: str | None = None
    manager_name: str | None = None
```

- [ ] **Step 2: Update interview_engine.create_session**

In `backend/app/services/interview_engine.py`, update `create_session` signature and body:

```python
async def create_session(
    self,
    user_id: str,
    company: str,
    role: str,
    round_types: list[str],
    career_track: str = "technology",
    level: str = "mid_level",
    interview_stage: str = "hr_interview",
    jd_text: str | None = None,
    manager_name: str | None = None,
) -> dict:
    import hashlib
    session = InterviewSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company=company,
        role=role,
        career_track=career_track,
        level=level,
        interview_stage=interview_stage,
        jd_hash=hashlib.sha256(jd_text.encode()).hexdigest() if jd_text else None,
    )
    self.db.add(session)

    first_round_type = round_types[0]
    round_ = Round(id=str(uuid.uuid4()), session_id=session.id, type=first_round_type)
    self.db.add(round_)
    await self.db.commit()

    # Use ContextAssembler instead of bare persona engine
    from app.services.context_assembler import ContextAssembler
    assembler = ContextAssembler(db=self.db)
    context = await assembler.assemble(
        user_id=user_id, company=company, role=role,
        career_track=career_track, level=level,
        interview_stage=interview_stage, jd_text=jd_text,
        manager_name=manager_name,
    )

    questions = await self.orchestrator.generate_questions(
        company=company, role=role, round_type=first_round_type,
        graph_context=context["graph_context"],
        knowledge_context=context["knowledge_profile"],
    )
    persona = await self._persona_engine.build(
        company=company, role=role, round_type=first_round_type
    )

    return {
        "session_id": session.id,
        "round_id": round_.id,
        "company": company,
        "role": role,
        "career_track": career_track,
        "level": level,
        "current_round": first_round_type,
        "remaining_rounds": round_types[1:],
        "questions": questions,
        "persona": persona,
    }
```

- [ ] **Step 3: Update sessions.py API route**

In `backend/app/api/v1/sessions.py`, update `create_session`:

```python
session = await engine.create_session(
    user_id=user_id,
    company=body.company,
    role=body.role,
    round_types=body.round_types,
    career_track=body.career_track,
    level=body.level,
    interview_stage=body.interview_stage,
    jd_text=body.jd_text,
    manager_name=body.manager_name,
)
```

- [ ] **Step 4: Update test_interview_engine mock**

In `backend/tests/services/test_interview_engine.py`, patch `ContextAssembler`:

```python
with patch("app.services.interview_engine.ContextAssembler") as MockCA:
    MockCA.return_value.assemble = AsyncMock(return_value={
        "knowledge_profile": {}, "jd_analysis": {},
        "graph_context": {}, "user_weak_dimensions": [],
    })
    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    engine._persona_engine = _mock_persona_engine()
    result = await engine.create_session("user1", "Google", "SWE", ["behavioral", "technical"])
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/services/test_interview_engine.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/session.py backend/app/services/interview_engine.py backend/app/api/v1/sessions.py backend/tests/services/test_interview_engine.py
git commit -m "feat(step-32): wire career context — track/level/stage through session creation, ContextAssembler integrated"
```

---

## Task 10: Universal Session Entry Form (Frontend)

**Files:**
- Create: `frontend/src/components/interview/SessionSetupForm.tsx`
- Modify: `frontend/src/store/interviewStore.ts`
- Modify: `frontend/src/hooks/useInterviewSession.ts`
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Add career_track + level to interviewStore**

In `frontend/src/store/interviewStore.ts`, add to `InterviewState`:

```typescript
careerTrack: string
level: string
interviewStage: string
```

Add to initial state and update `setSession` to accept these fields:

```typescript
setSession: (
  sessionId: string, company: string, role: string,
  round: Round, remainingRounds: string[], persona: string,
  careerTrack: string, level: string, interviewStage: string
) => set({ sessionId, company, role, currentRound: round, remainingRounds, persona,
            careerTrack, level, interviewStage, sessionComplete: false, roundFailed: false }),
```

- [ ] **Step 2: Update useInterviewSession.startSession**

In `frontend/src/hooks/useInterviewSession.ts`:

```typescript
const startSession = async (
  company: string, role: string, rounds: string[],
  careerTrack: string, level: string, interviewStage: string,
  jdText?: string, managerName?: string,
) => {
  const res = await apiFetch(`${API}/interview-sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company, role, round_types: rounds,
      career_track: careerTrack,
      level,
      interview_stage: interviewStage,
      jd_text: jdText || null,
      manager_name: managerName || null,
    }),
  })
  const { data } = await res.json()
  setSession(
    data.session_id, data.company, data.role,
    { id: data.round_id, type: data.current_round, questions: data.questions, currentQuestionIndex: 0 },
    data.remaining_rounds ?? [], data.persona,
    data.career_track, data.level, data.interview_stage ?? interviewStage,
  )
  return data
}
```

- [ ] **Step 3: Create SessionSetupForm.tsx**

```tsx
// frontend/src/components/interview/SessionSetupForm.tsx
import { useState } from 'react'
import { useInterviewSession } from '../../hooks/useInterviewSession'

const CAREER_TRACKS = [
  { value: 'technology', label: 'Technology' },
  { value: 'finance_fintech', label: 'Finance & Fintech' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'business_consulting', label: 'Business & Consulting' },
  { value: 'sales_marketing', label: 'Sales & Marketing' },
  { value: 'design_creative', label: 'Design & Creative' },
  { value: 'legal_compliance', label: 'Legal & Compliance' },
  { value: 'hr_people', label: 'HR & People' },
  { value: 'education_training', label: 'Education & Training' },
  { value: 'operations_supply_chain', label: 'Operations & Supply Chain' },
]

const LEVELS = [
  { value: 'entry_junior', label: 'Entry / Junior' },
  { value: 'mid_level', label: 'Mid-level' },
  { value: 'senior', label: 'Senior' },
  { value: 'lead_manager', label: 'Lead / Manager' },
  { value: 'director_vp_csuite', label: 'Director / VP / C-Suite' },
]

const STAGES = [
  { value: 'phone_screen', label: 'Phone Screen' },
  { value: 'hr_interview', label: 'HR Interview' },
  { value: 'hiring_manager', label: 'Hiring Manager' },
  { value: 'skills_domain', label: 'Skills / Domain' },
  { value: 'panel_interview', label: 'Panel Interview' },
  { value: 'case_presentation', label: 'Case / Presentation' },
  { value: 'final_executive', label: 'Final / Executive' },
  { value: 'offer_negotiation', label: 'Offer Negotiation' },
]

const ROUND_MAP: Record<string, string[]> = {
  phone_screen: ['behavioral'],
  hr_interview: ['behavioral'],
  hiring_manager: ['behavioral', 'technical'],
  skills_domain: ['technical'],
  panel_interview: ['behavioral', 'technical'],
  case_presentation: ['behavioral', 'technical'],
  final_executive: ['behavioral'],
  offer_negotiation: ['behavioral'],
}

const inputBase: React.CSSProperties = {
  background: 'rgba(7,15,28,0.8)',
  border: '1px solid rgba(34,211,238,0.15)',
  color: 'rgba(226,232,240,0.9)',
  fontFamily: 'monospace',
  fontSize: '13px',
  padding: '10px 14px',
  borderRadius: '6px',
  outline: 'none',
  width: '100%',
}

export default function SessionSetupForm() {
  const { startSession } = useInterviewSession()
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [track, setTrack] = useState('technology')
  const [level, setLevel] = useState('mid_level')
  const [stage, setStage] = useState('hr_interview')
  const [jdText, setJdText] = useState('')
  const [managerName, setManagerName] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const canStart = company.trim() && role.trim()

  const handleStart = async () => {
    if (!canStart) return
    setLoading(true)
    setError('')
    try {
      const rounds = ROUND_MAP[stage] ?? ['behavioral']
      await startSession(company, role, rounds, track, level, stage, jdText || undefined, managerName || undefined)
    } catch {
      setError('Failed to start session. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const labelStyle: React.CSSProperties = {
    color: 'rgba(34,211,238,0.45)',
    fontFamily: 'monospace',
    fontSize: '10px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.16em',
  }

  return (
    <div className="flex flex-col gap-5 w-full" style={{ maxWidth: '440px' }}>
      <div>
        <p style={{ ...labelStyle, marginBottom: '4px' }}>Interview Prep</p>
        <h2 style={{ color: 'rgba(226,232,240,0.95)', fontFamily: 'monospace', fontSize: '20px', fontWeight: 700, letterSpacing: '0.04em' }}>
          Prepare for your interview
        </h2>
      </div>

      {error && <p style={{ color: '#f87171', fontSize: '12px', fontFamily: 'monospace' }}>{error}</p>}

      {/* Row 1: Company + Role */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Company</label>
          <input style={inputBase} placeholder="e.g. Stripe" value={company} onChange={e => setCompany(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Role</label>
          <input style={inputBase} placeholder="e.g. CTO" value={role} onChange={e => setRole(e.target.value)} />
        </div>
      </div>

      {/* Row 2: Track */}
      <div className="flex flex-col gap-2">
        <label style={labelStyle}>Career Track</label>
        <div className="relative">
          <select style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
            value={track} onChange={e => setTrack(e.target.value)}>
            {CAREER_TRACKS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
        </div>
      </div>

      {/* Row 3: Level + Stage */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Seniority Level</label>
          <div className="relative">
            <select style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
              value={level} onChange={e => setLevel(e.target.value)}>
              {LEVELS.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <label style={labelStyle}>Interview Stage</label>
          <div className="relative">
            <select style={{ ...inputBase, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }}
              value={stage} onChange={e => setStage(e.target.value)}>
              {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <svg className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
          </div>
        </div>
      </div>

      {/* Advanced toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(v => !v)}
        style={{ color: 'rgba(34,211,238,0.5)', fontFamily: 'monospace', fontSize: '11px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0 }}
      >
        {showAdvanced ? '▲' : '▼'} {showAdvanced ? 'Hide' : 'Add'} job description / manager (optional)
      </button>

      {showAdvanced && (
        <>
          <div className="flex flex-col gap-2">
            <label style={labelStyle}>Job Description</label>
            <textarea
              style={{ ...inputBase, height: '96px', resize: 'none' }}
              placeholder="Paste the JD here for personalized questions…"
              value={jdText}
              onChange={e => setJdText(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label style={labelStyle}>Hiring Manager Name (optional)</label>
            <input style={inputBase} placeholder="e.g. Jane Doe" value={managerName} onChange={e => setManagerName(e.target.value)} />
          </div>
        </>
      )}

      <button
        disabled={!canStart || loading}
        onClick={handleStart}
        className="flex items-center justify-center gap-2 font-semibold text-xs uppercase tracking-[0.14em] py-3 rounded transition-all duration-150 disabled:opacity-30"
        style={{
          background: canStart ? 'rgba(34,211,238,0.1)' : 'rgba(34,211,238,0.04)',
          border: `1px solid ${canStart ? 'rgba(34,211,238,0.35)' : 'rgba(34,211,238,0.1)'}`,
          color: '#22d3ee',
          fontFamily: 'monospace',
        }}
      >
        {loading
          ? <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
        }
        {loading ? 'Starting…' : 'Start Prep Session'}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Replace CompanySelector with SessionSetupForm in Dashboard.tsx**

In `frontend/src/pages/Dashboard.tsx`, replace any `<CompanySelector` usage with `<SessionSetupForm />`.

- [ ] **Step 5: Manual smoke test**

1. Start backend + frontend
2. Open the dashboard
3. Fill in company, role, track, level, stage
4. Toggle "Add job description", paste a JD
5. Click Start — confirm session starts with correct round type

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/interview/SessionSetupForm.tsx frontend/src/store/interviewStore.ts frontend/src/hooks/useInterviewSession.ts frontend/src/pages/Dashboard.tsx
git commit -m "feat(step-28): universal session setup form — 10 tracks, 5 levels, 8 stages, JD injection"
```

---

## Task 11: Debrief Upgrade + Progress Writing

**Files:**
- Modify: `backend/app/services/debrief_service.py`

- [ ] **Step 1: Update debrief generate() to write progress scores**

In `backend/app/services/debrief_service.py`, at the end of `generate()` after the Claude/DeepSeek analysis, add:

```python
# Write skill dimension scores to user_progress
try:
    from app.services.progress_service import ProgressService
    progress_svc = ProgressService(db=self.db)
    # Map overall analysis to skill dimensions from knowledge profile
    dimension_scores = _extract_dimension_scores(analysis, rounds)
    career_track = getattr(session, 'career_track', None) or 'technology'
    level = getattr(session, 'level', None) or 'mid_level'
    stage = getattr(session, 'interview_stage', None) or 'hr_interview'
    await progress_svc.write_scores(
        user_id=session.user_id,
        session_id=session_id,
        career_track=career_track,
        level=level,
        stage=stage,
        scores=dimension_scores,
    )
except Exception:
    pass  # best-effort
```

Add helper function before the class:

```python
def _extract_dimension_scores(analysis: dict, rounds: list) -> dict[str, float]:
    """Derive per-dimension scores from analysis + round grades."""
    overall = float(analysis.get("overall_score", 5.0))
    # Base all dimensions on overall, then weight by analysis signals
    dims = {
        "domain_knowledge": overall,
        "communication_clarity": overall,
        "quantified_impact": overall * 0.9 if not analysis.get("improvements") else overall * 0.7,
        "leadership_narrative": overall,
        "culture_alignment": overall,
        "executive_presence": overall,
        "problem_solving": overall,
    }
    # Boost dimensions mentioned in strengths, lower ones in improvements
    for s in analysis.get("strengths", []):
        s_lower = s.lower()
        for dim in dims:
            if dim.replace("_", " ") in s_lower:
                dims[dim] = min(10.0, dims[dim] + 1.0)
    for imp in analysis.get("improvements", []):
        i_lower = imp.lower()
        for dim in dims:
            if dim.replace("_", " ") in i_lower:
                dims[dim] = max(0.0, dims[dim] - 1.5)
    return {k: round(v, 2) for k, v in dims.items()}
```

Also upgrade the debrief prompt to request an improvement plan:

```python
prompt = (
    f"You are reviewing an interview for {session.company}, role: {session.role}.\n\n"
    f"Transcript:\n{transcript}\n\nAverage score: {avg_score:.1f}/10\n\n"
    "Return a JSON debrief with improvement plan:\n"
    '{"overall_score": 7.5, "strengths": ["..."], "improvements": ["..."], '
    '"recommendation": "...", "top_3_focus_areas": ["area 1", "area 2", "area 3"], '
    '"recommended_next_session": "e.g. Practice Hiring Manager stage at Senior level"}'
)
```

Update the `generate()` return dict to include new fields:

```python
return {
    ...existing fields...,
    "top_3_focus_areas": analysis.get("top_3_focus_areas", []),
    "recommended_next_session": analysis.get("recommended_next_session", ""),
}
```

- [ ] **Step 2: Update DebriefReport.tsx to show new fields**

In `frontend/src/components/interview/DebriefReport.tsx`, add to `DebriefData` interface:

```typescript
top_3_focus_areas: string[]
recommended_next_session: string
```

Add a "Focus Areas" card after the improvements block:

```tsx
{data.top_3_focus_areas?.length > 0 && (
  <div className="bg-gray-900 rounded-2xl p-5">
    <h2 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-3">Top 3 Focus Areas</h2>
    <ol className="space-y-1.5 list-decimal list-inside">
      {data.top_3_focus_areas.map((area, i) => (
        <li key={i} className="text-sm text-gray-300">{area}</li>
      ))}
    </ol>
  </div>
)}

{data.recommended_next_session && (
  <div className="bg-cyan-950 border border-cyan-800 rounded-2xl p-5">
    <h2 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-1">Recommended Next Session</h2>
    <p className="text-sm text-cyan-200">{data.recommended_next_session}</p>
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/debrief_service.py frontend/src/components/interview/DebriefReport.tsx
git commit -m "feat(step-34): debrief upgrade — DeepSeek-R1 improvement plan, top 3 focus areas, progress scores written"
```

---

## Task 12: Progress Dashboard

**Files:**
- Create: `frontend/src/hooks/useProgress.ts`
- Create: `frontend/src/components/interview/ProgressDashboard.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Install Recharts**

```bash
cd frontend && npm install recharts
```

- [ ] **Step 2: Create useProgress hook**

```typescript
// frontend/src/hooks/useProgress.ts
import { useState, useEffect } from 'react'
import { apiFetch } from '../lib/apiFetch'

const API = 'http://localhost:8000/api/v1'

interface ProgressSummary {
  dimensions: Record<string, number>
  total_sessions: number
  average_score: number
}

export function useProgress() {
  const [data, setData] = useState<ProgressSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch(`${API}/progress/me`)
      .then(r => r.json())
      .then(j => setData(j.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return { data, loading }
}
```

- [ ] **Step 3: Create ProgressDashboard.tsx**

```tsx
// frontend/src/components/interview/ProgressDashboard.tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadialBarChart, RadialBar, BarChart, Bar, Cell,
} from 'recharts'
import { useProgress } from '../../hooks/useProgress'

const DIMENSION_LABELS: Record<string, string> = {
  domain_knowledge: 'Domain Knowledge',
  communication_clarity: 'Communication',
  quantified_impact: 'Quantified Impact',
  leadership_narrative: 'Leadership',
  culture_alignment: 'Culture Fit',
  executive_presence: 'Executive Presence',
  problem_solving: 'Problem Solving',
}

function barColor(score: number) {
  if (score >= 7) return '#22c55e'
  if (score >= 5) return '#f59e0b'
  return '#ef4444'
}

export default function ProgressDashboard({ onStartNew }: { onStartNew: () => void }) {
  const { data, loading } = useProgress()

  const avgPct = data ? Math.round((data.average_score / 10) * 100) : 0

  const dimensionBars = data
    ? Object.entries(data.dimensions).map(([dim, score]) => ({
        name: DIMENSION_LABELS[dim] ?? dim,
        score: Math.round(score * 10) / 10,
        pct: Math.round((score / 10) * 100),
      }))
    : []

  const donutData = [{ name: 'Score', value: avgPct, fill: '#22d3ee' }]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p style={{ color: 'rgba(34,211,238,0.4)', fontFamily: 'monospace', fontSize: '13px' }}>
          Loading progress…
        </p>
      </div>
    )
  }

  if (!data || data.total_sessions === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p style={{ color: 'rgba(226,232,240,0.4)', fontFamily: 'monospace', fontSize: '13px' }}>
          Complete your first session to see progress
        </p>
        <button
          onClick={onStartNew}
          style={{
            background: 'rgba(34,211,238,0.1)',
            border: '1px solid rgba(34,211,238,0.35)',
            color: '#22d3ee',
            fontFamily: 'monospace',
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.14em',
            padding: '8px 20px',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          Start First Session
        </button>
      </div>
    )
  }

  return (
    <div className="w-full space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        {[
          { label: 'Sessions Taken', value: data.total_sessions, suffix: '' },
          { label: 'Average Score', value: `${avgPct}%`, suffix: '' },
          {
            label: 'Strongest Skill',
            value: dimensionBars.length
              ? DIMENSION_LABELS[Object.entries(data.dimensions).sort((a, b) => b[1] - a[1])[0]?.[0]] ?? '—'
              : '—',
            suffix: '',
          },
          {
            label: 'Needs Work',
            value: dimensionBars.length
              ? DIMENSION_LABELS[Object.entries(data.dimensions).sort((a, b) => a[1] - b[1])[0]?.[0]] ?? '—'
              : '—',
            suffix: '',
          },
        ].map((card) => (
          <div
            key={card.label}
            style={{
              background: 'rgba(7,15,28,0.6)',
              border: '1px solid rgba(34,211,238,0.1)',
              borderRadius: '10px',
              padding: '16px',
            }}
          >
            <p style={{ color: 'rgba(34,211,238,0.45)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '6px' }}>
              {card.label}
            </p>
            <p style={{ color: 'rgba(226,232,240,0.9)', fontFamily: 'monospace', fontSize: '22px', fontWeight: 700 }}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Skill Breakdown */}
      <div
        style={{
          background: 'rgba(7,15,28,0.6)',
          border: '1px solid rgba(34,211,238,0.1)',
          borderRadius: '10px',
          padding: '20px',
        }}
      >
        <div className="flex items-start gap-6">
          {/* Donut */}
          <div style={{ width: 120, height: 120, flexShrink: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart innerRadius={32} outerRadius={52} data={donutData} startAngle={90} endAngle={-270}>
                <RadialBar dataKey="value" cornerRadius={6} background={{ fill: 'rgba(34,211,238,0.08)' }} />
              </RadialBarChart>
            </ResponsiveContainer>
            <p style={{ textAlign: 'center', color: 'rgba(226,232,240,0.8)', fontFamily: 'monospace', fontSize: '14px', fontWeight: 700, marginTop: '-64px' }}>
              {avgPct}%
            </p>
          </div>

          {/* Bars */}
          <div className="flex-1 space-y-2">
            <p style={{ color: 'rgba(34,211,238,0.45)', fontFamily: 'monospace', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '10px' }}>
              Skill Breakdown
            </p>
            {dimensionBars.map((d) => (
              <div key={d.name} className="flex items-center gap-3">
                <span style={{ color: 'rgba(226,232,240,0.6)', fontFamily: 'monospace', fontSize: '11px', width: '130px', flexShrink: 0 }}>
                  {d.name}
                </span>
                <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${d.pct}%`, height: '100%', background: barColor(d.score), borderRadius: '3px', transition: 'width 0.6s ease' }} />
                </div>
                <span style={{ color: 'rgba(226,232,240,0.5)', fontFamily: 'monospace', fontSize: '11px', width: '36px', textAlign: 'right' }}>
                  {d.pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={onStartNew}
        style={{
          width: '100%',
          background: 'rgba(34,211,238,0.08)',
          border: '1px solid rgba(34,211,238,0.2)',
          color: '#22d3ee',
          fontFamily: 'monospace',
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.14em',
          padding: '12px',
          borderRadius: '8px',
          cursor: 'pointer',
        }}
      >
        + Start New Session
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Wire ProgressDashboard into Dashboard.tsx**

In `frontend/src/pages/Dashboard.tsx`, import `ProgressDashboard` and `SessionSetupForm`. Show `ProgressDashboard` alongside `SessionSetupForm`:

```tsx
import ProgressDashboard from '../components/interview/ProgressDashboard'
import SessionSetupForm from '../components/interview/SessionSetupForm'

// In the dashboard layout, render both side-by-side or stacked:
<div className="flex gap-8 w-full max-w-5xl">
  <div style={{ flex: '0 0 440px' }}>
    <SessionSetupForm />
  </div>
  <div className="flex-1">
    <ProgressDashboard onStartNew={() => {/* focus SessionSetupForm */}} />
  </div>
</div>
```

- [ ] **Step 5: Manual verification**

1. Complete 1–2 sessions
2. Open dashboard — confirm stat cards show correct values
3. Confirm skill bars render with correct colors
4. Confirm empty state shows "Start First Session" before any sessions

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useProgress.ts frontend/src/components/interview/ProgressDashboard.tsx frontend/src/pages/Dashboard.tsx
git commit -m "feat(step-35): progress dashboard — stat cards, skill breakdown donut + bars, Recharts, matches reference design"
```

---

## Task 13: Browser TTS (Replace OpenAI TTS)

**Files:**
- Modify: `frontend/src/hooks/useVoice.ts`

- [ ] **Step 1: Read current useVoice.ts**

```bash
cat frontend/src/hooks/useVoice.ts
```

- [ ] **Step 2: Replace TTS with Web Speech API**

In `frontend/src/hooks/useVoice.ts`, replace the `speak` function with:

```typescript
const speak = (text: string) => {
  if (!text || typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.rate = 0.95
  utterance.pitch = 1.0
  utterance.volume = 1.0
  // Use the first English voice available, fallback to default
  const voices = window.speechSynthesis.getVoices()
  const enVoice = voices.find(v => v.lang.startsWith('en') && !v.name.includes('Google'))
  if (enVoice) utterance.voice = enVoice
  window.speechSynthesis.speak(utterance)
}
```

Remove the `POST /api/v1/speech/synthesize` fetch call entirely from this hook.

- [ ] **Step 3: Manual test**

Start the app, start a session — confirm questions are spoken using the browser's native voice with no API call to the backend.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useVoice.ts
git commit -m "feat(step-36): browser TTS — replace OpenAI TTS with Web Speech API, zero cost"
```

---

## Task 14: Offer Negotiation Module

**Files:**
- Modify: `backend/app/graph/knowledge_seed.py`
- No new files needed — reuses existing session engine

- [ ] **Step 1: Add offer_negotiation profiles to seed**

In `backend/app/graph/knowledge_seed.py`, add `"offer_negotiation"` as a second stage in the seed. After the loop that seeds `hr_interview` profiles, add:

```python
NEGOTIATION_PROFILES = {
    track: {
        "core_competencies": ["salary research", "value articulation", "BATNA awareness", "negotiation framing", "package components"],
        "question_archetypes": [
            {"type": "situational", "framework": "open", "weight": 0.4,
             "example": f"What salary range are you targeting for this {TRACK_DATA[track]['label']} role?"},
            {"type": "behavioral", "framework": "STAR", "weight": 0.3,
             "example": "Tell me about a time you successfully negotiated a compensation package."},
            {"type": "situational", "framework": "open", "weight": 0.3,
             "example": "The offer is 10% below your target. How do you respond?"},
        ],
        "evaluation_rubrics": RUBRICS,
        "answer_frameworks": ["BATNA", "STAR"],
        "common_pitfalls": [
            "Anchoring too low before the company makes an offer",
            "Negotiating only salary and ignoring total comp",
            "Accepting immediately without considering",
        ],
        "red_flags": ["Ultimatums", "Emotional reactions", "No market research"],
        "skill_dimensions": ["communication_clarity", "quantified_impact", "executive_presence"],
    }
    for track in TRACKS
}
```

Then in `seed_knowledge_profiles`, add `offer_negotiation` to the two existing stage calls:

```python
async def seed_knowledge_profiles(db: AsyncSession) -> None:
    await _seed_stage(db, "hr_interview")      # 50 profiles
    await _seed_stage(db, "skills_domain")     # 50 profiles
    # Offer negotiation: uses NEGOTIATION_PROFILES override, not _build_profile
    for track in TRACKS:
        for level in LEVELS:
            existing = await db.execute(
                select(KnowledgeProfile).where(
                    KnowledgeProfile.track == track,
                    KnowledgeProfile.level == level,
                    KnowledgeProfile.stage == "offer_negotiation",
                )
            )
            if existing.scalar_one_or_none():
                continue
            neg_profile = {**NEGOTIATION_PROFILES[track], "track": track, "level": level, "stage": "offer_negotiation"}
            db.add(KnowledgeProfile(
                id=str(uuid.uuid4()),
                track=track, level=level, stage="offer_negotiation",
                profile=neg_profile,
            ))
    await db.commit()
```

- [ ] **Step 2: Verify offer_negotiation stage works end-to-end**

1. Start backend (`docker-compose up -d && uvicorn app.main:app --reload`)
2. Verify seed logs show 150 profiles created (50 hr_interview + 50 skills_domain + 50 offer_negotiation)
3. Start a session with stage = `"offer_negotiation"` via the UI
4. Confirm negotiation-specific questions are generated

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph/knowledge_seed.py
git commit -m "feat(step-39): offer negotiation module — 50 negotiation profiles seeded across all tracks and levels"
```

---

## Running the Full Test Suite

```bash
# Backend
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend
cd frontend && npx vitest run

# Coverage target: 80% on all new service files
```

---

## Verification Checklist

Before marking this plan complete:

- [ ] All 10 career tracks produce track-appropriate questions (manual smoke test: 1 session per track)
- [ ] Context injection: session with JD produces different questions than session without JD on same role
- [ ] Debrief shows top_3_focus_areas referencing specific transcript content
- [ ] Progress dashboard stat cards match values in `user_progress` table
- [ ] Browser TTS works with no backend call for speech
- [ ] Full session cost (check DeepSeek dashboard): under $0.02
- [ ] All backend tests pass: `pytest tests/ -v`
