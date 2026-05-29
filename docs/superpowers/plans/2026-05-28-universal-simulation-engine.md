# Universal Simulation Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Simulation Builder UI to a universal backend that handles voice-first, time-enforced, AI-driven simulations for any scenario (pitch, MR review, teaching, behavioral, etc.)

**Architecture:** New `SimulationSession` layer runs in parallel to the existing `InterviewSession` system with zero shared tables (except `UserProgress`, which gets its FK constraint dropped). The engine is scenario-agnostic — all behavior flows from the `brief` JSONB. A Redis-backed hard-cutoff timer kills in-flight LLM streams on the server side.

**Tech Stack:** FastAPI + SQLAlchemy 2.x async, PostgreSQL JSONB, Redis (SESSION_TTL=4h), DeepSeek V3/R1 via OpenAI-compatible client, OpenAI TTS streaming, Deepgram voice, Zustand + React

---

## File Map

**Backend — create:**
- `backend/app/models/pg/simulation.py` — 3 ORM models (SimulationSession, SimulationTurn, SimulationDebrief)
- `backend/app/schemas/simulation.py` — Pydantic request/response shapes
- `backend/app/services/simulation_engine.py` — session lifecycle, hard cutoff, debrief trigger
- `backend/app/services/sim_llm_orchestrator.py` — scenario-agnostic prompts, DeepSeek calls
- `backend/app/services/sim_debrief_service.py` — debrief PDF generation (adapted from existing debrief_service)
- `backend/app/api/v1/sim_sessions.py` — REST + WebSocket handler
- `backend/migrations/versions/h2i3j4k5l6m7_add_simulation_tables.py` — creates 3 tables, drops UserProgress FK

**Backend — modify:**
- `backend/app/models/pg/__init__.py` — import new models so Alembic sees them
- `backend/app/api/v1/__init__.py` — register `sim_sessions` router (currently 1-line empty file)
- `backend/app/main.py` — `app.include_router(sim_sessions_router, prefix="/api/v1")`
- `backend/app/services/speech_service.py` — add `synthesize_stream` async generator

> **Note on migration path:** The spec says `backend/alembic/versions/` but the actual project uses `backend/migrations/versions/` (confirmed by `ls`). All migration tasks use the correct `migrations/` path.

**Frontend — create:**
- `frontend/src/store/simulationStore.ts` — Zustand store (activeSimSessionId, persona, timeBudget, scenarioType)
- `frontend/src/hooks/useSimulationSession.ts` — WS lifecycle, timer, voice pipeline
- `frontend/src/pages/SimulationSessionPage.tsx` — thin page wrapper
- `frontend/src/components/simulation/SimulationSession.tsx` — 3-zone layout (transcript, timer, context)
- `frontend/src/components/simulation/SimulationDebrief.tsx` — scores, bars, PDF download

**Frontend — modify:**
- `frontend/src/components/interview/SimulationBuilder.tsx` — wire `onLaunch` to POST + store
- `frontend/src/App.tsx` — add `useSimulationStore` check above Dashboard render

---

## Task 1: ORM Models

**Files:**
- Create: `backend/app/models/pg/simulation.py`
- Modify: `backend/app/models/pg/__init__.py`

- [ ] **Step 1: Write the models file**

```python
# backend/app/models/pg/simulation.py
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, DateTime, Boolean, Float, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.pg.base import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False)  # no FK — logical link only
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brief: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSONB, default=list)
    time_budget_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hard_cutoff_fired: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)


class SimulationTurn(Base):
    __tablename__ = "simulation_turns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String, nullable=False)  # logical FK to simulation_sessions
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)   # "user" | "ai"
    modality: Mapped[str] = mapped_column(String(10), nullable=False)  # "voice" | "text"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    time_offset_seconds: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[list | None] = mapped_column(JSONB, default=list)
    emotion_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rewrite_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class SimulationDebrief(Base):
    __tablename__ = "simulation_debriefs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String, nullable=False)  # logical FK
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hire_signal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    core_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scenario_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[list | None] = mapped_column(JSONB, default=list)
    improvements: Mapped[list | None] = mapped_column(JSONB, default=list)
    focus_areas: Mapped[list | None] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

- [ ] **Step 2: Register models in `__init__.py`**

Open `backend/app/models/pg/__init__.py`. It is currently empty (1 line). Add:
```python
from app.models.pg.simulation import SimulationSession, SimulationTurn, SimulationDebrief  # noqa: F401
```

- [ ] **Step 3: Commit**
```bash
cd backend
git add app/models/pg/simulation.py app/models/pg/__init__.py
git commit -m "feat(sim): add ORM models for SimulationSession, SimulationTurn, SimulationDebrief"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/migrations/versions/h2i3j4k5l6m7_add_simulation_tables.py`

- [ ] **Step 1: Write the migration**

```python
# backend/migrations/versions/h2i3j4k5l6m7_add_simulation_tables.py
"""add simulation tables and drop user_progress session_id FK

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'simulation_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('scenario_type', sa.String(50), nullable=True),
        sa.Column('brief', JSONB(), nullable=True),
        sa.Column('attachments', JSONB(), nullable=True),
        sa.Column('time_budget_seconds', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('hard_cutoff_fired', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('persona', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'simulation_turns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('speaker', sa.String(10), nullable=False),
        sa.Column('modality', sa.String(10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('audio_url', sa.String(512), nullable=True),
        sa.Column('time_offset_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('tool_calls', JSONB(), nullable=True),
        sa.Column('emotion_state', sa.String(50), nullable=True),
        sa.Column('rewrite_count', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'simulation_debriefs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('scenario_type', sa.String(50), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('hire_signal', sa.String(20), nullable=True),
        sa.Column('core_scores', JSONB(), nullable=True),
        sa.Column('scenario_scores', JSONB(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('strengths', JSONB(), nullable=True),
        sa.Column('improvements', JSONB(), nullable=True),
        sa.Column('focus_areas', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Drop FK constraint on user_progress.session_id so simulation session IDs
    # don't cause violations (simulation_sessions ≠ interview sessions table).
    # The column stays as a plain String — logical link only.
    # NOTE: The actual constraint name may differ. Run this to find it first:
    #   SELECT conname FROM pg_constraint WHERE conrelid = 'user_progress'::regclass;
    # Then replace 'user_progress_session_id_fkey' below with the real name if different.
    try:
        op.drop_constraint('user_progress_session_id_fkey', 'user_progress', type_='foreignkey')
    except Exception:
        pass  # Already dropped or constraint name differs — handled gracefully


def downgrade() -> None:
    op.drop_table('simulation_debriefs')
    op.drop_table('simulation_turns')
    op.drop_table('simulation_sessions')
    op.create_foreign_key(
        'user_progress_session_id_fkey',
        'user_progress', 'sessions',
        ['session_id'], ['id'],
    )
```

- [ ] **Step 2: Run the migration**
```bash
cd backend
source venv/Scripts/activate  # or venv/bin/activate on Linux
alembic upgrade head
```
Expected output: `Running upgrade g1h2i3j4k5l6 -> h2i3j4k5l6m7, add simulation tables...`

- [ ] **Step 3: Verify tables exist**
```bash
# Connect to postgres and check:
# \dt simulation_* should show 3 tables
# \d user_progress should show session_id with NO FK constraint
```

- [ ] **Step 4: Commit**
```bash
git add migrations/versions/h2i3j4k5l6m7_add_simulation_tables.py
git commit -m "feat(sim): migration — add simulation tables, drop user_progress session_id FK"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/simulation.py`

- [ ] **Step 1: Write schemas**

```python
# backend/app/schemas/simulation.py
from pydantic import BaseModel
from typing import Any


class CreateSimSessionRequest(BaseModel):
    brief: dict[str, Any]
    attachments: list[dict[str, Any]] = []


class SimTurnRequest(BaseModel):
    content: str
    modality: str = "text"   # "voice" | "text"
    time_offset_seconds: int = 0


class SimSessionResponse(BaseModel):
    session_id: str
    persona: str
    time_budget_seconds: int | None
    scenario_type: str
    started_at: str


class SimTurnResponse(BaseModel):
    response: str
    tool_events: list[dict[str, Any]] = []
    time_remaining_seconds: int | None
    session_complete: bool = False
    cutoff: bool = False


class CoreScores(BaseModel):
    communication: float
    time_management: float
    pressure_handling: float
    structure: float
    depth: float


class SimDebriefResponse(BaseModel):
    id: str
    session_id: str
    scenario_type: str | None
    overall_score: float | None
    hire_signal: str | None
    core_scores: dict[str, Any] | None
    scenario_scores: dict[str, Any] | None
    summary: str | None
    strengths: list[str]
    improvements: list[str]
    focus_areas: list[str]
    created_at: str
```

- [ ] **Step 2: Verify no import errors**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.schemas.simulation import CreateSimSessionRequest, SimDebriefResponse; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add app/schemas/simulation.py
git commit -m "feat(sim): pydantic schemas for simulation session API"
```

---

## Task 4: SpeechService — Streaming TTS

**Files:**
- Modify: `backend/app/services/speech_service.py`

- [ ] **Step 1: Add `synthesize_stream` method**

In `speech_service.py`, after the `synthesize` method, add:

```python
    async def synthesize_stream(self, text: str):
        """Yield MP3 chunks as bytes using OpenAI streaming TTS."""
        async with self._openai_client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=text,
            response_format="mp3",
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk
```

- [ ] **Step 2: Verify import works**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.services.speech_service import SpeechService; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add app/services/speech_service.py
git commit -m "feat(sim): add synthesize_stream to SpeechService for chunk-based TTS"
```

---

## Task 5: SimLLMOrchestrator

**Files:**
- Create: `backend/app/services/sim_llm_orchestrator.py`

- [ ] **Step 1: Write the orchestrator**

```python
# backend/app/services/sim_llm_orchestrator.py
import json
import re
import openai
from dataclasses import dataclass, field
from app.core.config import settings


@dataclass
class ToolCall:
    tool: str           # "terminal" | "code" | "file"
    command: str
    output: str = ""
    duration_ms: int = 0


@dataclass
class SimResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    end_signal: bool = False


@dataclass
class DebriefResult:
    overall_score: float
    hire_signal: str
    core_scores: dict
    scenario_scores: dict
    summary: str
    strengths: list
    improvements: list
    focus_areas: list


class SimLLMOrchestrator:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self._fast = "deepseek-chat"
        self._think = "deepseek-reasoner"

    async def _call(self, prompt: str, think: bool = False) -> str:
        model = self._think if think else self._fast
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    def _parse_json(self, raw: str, fallback: dict) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            return {**fallback, **json.loads(raw)}
        except (json.JSONDecodeError, TypeError):
            m = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                return {**fallback, **json.loads(m.group())} if m else fallback
            except (json.JSONDecodeError, AttributeError):
                return fallback

    def _get_field(self, brief: dict, name: str) -> str:
        """Extract a field value from brief.fields list by label."""
        for f in brief.get("fields", []):
            if isinstance(f, dict) and f.get("label", "").lower() == name.lower():
                return f.get("value", "")
        return ""

    async def build_sim_persona(self, brief: dict) -> str:
        role_playing = self._get_field(brief, "I'll play")
        pressure = self._get_field(brief, "Pressure")
        summary = brief.get("summaryParts", ["a simulation"])
        prompt = (
            f"You are about to play a character in a simulation. "
            f"Your character: {role_playing}. "
            f"Pressure level: {pressure}. "
            f"Context: {' '.join(summary) if isinstance(summary, list) else summary}\n\n"
            "Write a 2-3 sentence internal character note describing exactly how this character "
            "speaks, what they care about, and how they push back. Be concrete, no fluff. "
            "This is a private note — write as if briefing an actor."
        )
        return await self._call(prompt)

    async def respond(
        self,
        brief: dict,
        turns: list[dict],
        user_content: str,
        attachment_context: str,
        time_remaining_pct: float,
    ) -> SimResponse:
        scenario = self._get_field(brief, "Scenario")
        format_field = self._get_field(brief, "Format")
        push_on = self._get_field(brief, "I'll push on")
        persona_note = brief.get("_persona", "")

        time_pressure = ""
        if time_remaining_pct < 0.10:
            time_pressure = "CRITICAL: Less than 10% of time remains. You may cut off mid-sentence if needed. Be very direct."
        elif time_remaining_pct < 0.20:
            time_pressure = "Time is running short. Be more pressing and direct."

        history = "\n".join(
            f"[{t['speaker'].upper()}] {t['content']}"
            for t in (turns[-20:] if len(turns) > 20 else turns)
        )

        tool_instruction = (
            'If you need to run code or read a file, reply with JSON in this exact format: '
            '{"tool": "terminal", "command": "<shell command>"} — on its own line before your spoken response. '
            'For file reads: {"tool": "file", "command": "<path>"}. '
            'For code execution: {"tool": "code", "command": "<python code>"}. '
            'You may only use a tool if the attachment context shows files or code are available.'
            if attachment_context else
            ""
        )

        prompt = f"""You are playing this character:
{persona_note}

Scenario: {scenario}
Format: {format_field}
Push on: {push_on}
{time_pressure}

Attached context (pre-analyzed — you know this already, simulate discovering it live):
{attachment_context or "No attachments."}

Conversation so far:
{history}

[USER]: {user_content}

{tool_instruction}

Respond as your character now. Stay in role. One focused response — no rambling.
If the simulation is naturally complete (e.g. Q&A period ended, session goal achieved), 
add a final line: END_SESSION"""

        raw = await self._call(prompt)

        # Detect tool call
        tool_calls: list[ToolCall] = []
        tool_match = re.search(r'\{"tool":\s*"([^"]+)",\s*"command":\s*"([^"]+)"\}', raw)
        if tool_match:
            tool_calls.append(ToolCall(tool=tool_match.group(1), command=tool_match.group(2)))
            raw = raw[:tool_match.start()].strip() + raw[tool_match.end():].strip()

        end_signal = "END_SESSION" in raw
        text = raw.replace("END_SESSION", "").strip()

        return SimResponse(text=text, tool_calls=tool_calls, end_signal=end_signal)

    async def debrief(self, brief: dict, turns: list[dict], think: bool = True) -> DebriefResult:
        scenario = self._get_field(brief, "Scenario")
        format_field = self._get_field(brief, "Format")
        transcript = "\n".join(
            f"[{t['speaker'].upper()} t={t.get('time_offset_seconds', 0)}s] {t['content']}"
            for t in turns
        )

        fallback = {
            "overall_score": 5.0,
            "hire_signal": "borderline",
            "core_scores": {
                "communication": 5.0, "time_management": 5.0,
                "pressure_handling": 5.0, "structure": 5.0, "depth": 5.0,
            },
            "scenario_scores": {},
            "summary": "Unable to generate debrief.",
            "strengths": [],
            "improvements": [],
            "focus_areas": [],
        }

        prompt = f"""You are an expert evaluator. Analyze this simulation transcript and return structured JSON feedback.

Scenario: {scenario}
Format: {format_field}

Transcript:
{transcript}

Return ONLY valid JSON with this exact structure:
{{
  "overall_score": <float 0-10>,
  "hire_signal": "<strong_yes|yes|borderline|no|strong_no>",
  "core_scores": {{
    "communication": <0-10>,
    "time_management": <0-10>,
    "pressure_handling": <0-10>,
    "structure": <0-10>,
    "depth": <0-10>
  }},
  "scenario_scores": {{
    "<dimension_name>": <0-10>,
    ...  (2-4 dimensions specific to THIS scenario format, you decide what matters)
  }},
  "summary": "<2-3 sentence honest summary>",
  "strengths": ["<specific strength>", ...],
  "improvements": ["<specific improvement>", ...],
  "focus_areas": ["<top focus>", "<second>", "<third>"]
}}"""

        raw = await self._call(prompt, think=think)
        data = self._parse_json(raw, fallback)
        return DebriefResult(
            overall_score=float(data.get("overall_score", 5.0)),
            hire_signal=data.get("hire_signal", "borderline"),
            core_scores=data.get("core_scores", fallback["core_scores"]),
            scenario_scores=data.get("scenario_scores", {}),
            summary=data.get("summary", ""),
            strengths=data.get("strengths", []),
            improvements=data.get("improvements", []),
            focus_areas=data.get("focus_areas", []),
        )
```

- [ ] **Step 2: Verify imports**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.services.sim_llm_orchestrator import SimLLMOrchestrator, SimResponse; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add app/services/sim_llm_orchestrator.py
git commit -m "feat(sim): SimLLMOrchestrator — scenario-agnostic prompts, DeepSeek V3/R1"
```

---

## Task 6: SimulationEngine

**Files:**
- Create: `backend/app/services/simulation_engine.py`

- [ ] **Step 1: Write the engine**

```python
# backend/app/services/simulation_engine.py
import re
import json
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.pg.simulation import SimulationSession, SimulationTurn, SimulationDebrief
from app.models.pg.progress import UserProgress
from app.services.sim_llm_orchestrator import SimLLMOrchestrator
from app.core.cache import get_redis, cache_set, cache_get, SESSION_TTL
import logging

logger = logging.getLogger(__name__)

SCENARIO_TYPE_MAP = [
    (re.compile(r"pitch|elevator|verbal pitch", re.I),         "pitch"),
    (re.compile(r"mr review|merge request|code review", re.I), "mr_review"),
    (re.compile(r"system design|architecture", re.I),          "system_design"),
    (re.compile(r"teach|lesson|class|student", re.I),          "teaching"),
    (re.compile(r"behavioral|star|panel", re.I),               "behavioral"),
    (re.compile(r"pair.program|live cod", re.I),               "mr_review"),
    (re.compile(r"negotiat|sales", re.I),                      "negotiation"),
]

CAREER_TRACK_MAP = {
    "pitch": "sales_marketing",
    "mr_review": "technology",
    "system_design": "technology",
    "teaching": "education_training",
    "behavioral": "technology",
    "negotiation": "sales_marketing",
    "custom": "technology",
}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_time_budget(time_str: str) -> int | None:
    if not time_str:
        return None
    low = time_str.lower()
    if "open" in low or "no limit" in low or "unlimited" in low:
        return None
    m = re.search(r'(\d+)\s*(hour|hr)', low)
    if m:
        return int(m.group(1)) * 3600
    m = re.search(r'(\d+)\s*min', low)
    if m:
        return int(m.group(1)) * 60
    m = re.search(r'(\d+)\s*sec', low)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)', low)
    if m:
        return int(m.group(1)) * 60  # bare number → minutes
    return None


def _detect_scenario_type(brief: dict) -> str:
    format_val = ""
    for f in brief.get("fields", []):
        if isinstance(f, dict) and f.get("label", "").lower() == "format":
            format_val = f.get("value", "")
            break
    for pattern, stype in SCENARIO_TYPE_MAP:
        if pattern.search(format_val):
            return stype
    return "custom"


def _get_field(brief: dict, name: str) -> str:
    for f in brief.get("fields", []):
        if isinstance(f, dict) and f.get("label", "").lower() == name.lower():
            return f.get("value", "")
    return ""


def _detect_level(brief: dict) -> str:
    plays = _get_field(brief, "I'll play").lower()
    if any(w in plays for w in ["junior", "entry", "intern", "graduate"]):
        return "entry_level"
    if any(w in plays for w in ["senior", "staff", "principal", "lead"]):
        return "senior"
    return "mid_level"


class SimulationEngine:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._orchestrator = SimLLMOrchestrator()

    async def create_session(self, user_id: str, brief: dict, attachments: list) -> dict:
        """Create session, pre-load attachments, build persona. Returns session dict."""
        time_field = _get_field(brief, "Time")
        time_budget = _parse_time_budget(time_field)
        scenario_type = _detect_scenario_type(brief)

        # Pre-analyze attachments (store in Redis for session lifetime)
        attachment_analysis = await self._preload_attachments(attachments)

        # Build AI persona
        persona = await self._orchestrator.build_sim_persona(brief)
        brief["_persona"] = persona  # embed persona into brief for later prompts

        session = SimulationSession(
            id=str(uuid4()),
            user_id=user_id,
            scenario_type=scenario_type,
            brief=brief,
            attachments=attachments,
            time_budget_seconds=time_budget,
            persona=persona,
        )
        self._db.add(session)
        await self._db.commit()

        # Cache attachments under sim namespace
        redis_key = f"sim:{session.id}:attachments"
        r = await get_redis()
        await r.setex(redis_key, SESSION_TTL, json.dumps(attachment_analysis))

        return {
            "session_id": session.id,
            "persona": persona,
            "time_budget_seconds": time_budget,
            "scenario_type": scenario_type,
            "started_at": session.started_at.isoformat(),
        }

    async def _preload_attachments(self, attachments: list) -> str:
        """Read attachment content. Returns a string context block for the LLM."""
        if not attachments:
            return ""
        lines = []
        for att in attachments:
            name = att.get("name", "unnamed")
            kind = att.get("kind", "file")
            content = att.get("content_preview", "")
            lines.append(f"[{kind.upper()}] {name}:\n{content}\n")
        return "\n".join(lines)

    async def submit_turn(
        self,
        session_id: str,
        content: str,
        modality: str,
        time_offset_seconds: int,
    ) -> dict:
        """Process one user turn. Returns AI response dict."""
        result = await self._db.execute(
            select(SimulationSession).where(SimulationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return {"error": "Session not found"}

        # Hard cutoff check
        elapsed = (utcnow() - session.started_at).total_seconds()
        if session.time_budget_seconds and elapsed >= session.time_budget_seconds:
            await self._db.execute(
                update(SimulationSession)
                .where(SimulationSession.id == session_id)
                .values(hard_cutoff_fired=True, ended_at=utcnow())
            )
            await self._db.commit()
            return {"cutoff": True, "response": "[HARD STOP]", "session_complete": True}

        # Fetch existing turns
        turns_result = await self._db.execute(
            select(SimulationTurn)
            .where(SimulationTurn.session_id == session_id)
            .order_by(SimulationTurn.seq)
        )
        turns = [
            {"speaker": t.speaker, "content": t.content, "time_offset_seconds": t.time_offset_seconds}
            for t in turns_result.scalars().all()
        ]

        # Current seq
        seq = len(turns)

        # Save user turn
        user_turn = SimulationTurn(
            session_id=session_id,
            seq=seq,
            speaker="user",
            modality=modality,
            content=content,
            time_offset_seconds=time_offset_seconds,
        )
        self._db.add(user_turn)
        await self._db.flush()

        # Get attachment context from Redis
        r = await get_redis()
        raw = await r.get(f"sim:{session_id}:attachments")
        attachment_context = raw or ""

        # Compute time remaining
        time_remaining = None
        time_remaining_pct = 1.0
        if session.time_budget_seconds:
            remaining = session.time_budget_seconds - elapsed
            time_remaining = max(0, int(remaining))
            time_remaining_pct = remaining / session.time_budget_seconds

        brief = session.brief or {}

        # Call LLM
        sim_response = await self._orchestrator.respond(
            brief=brief,
            turns=turns,
            user_content=content,
            attachment_context=attachment_context,
            time_remaining_pct=time_remaining_pct,
        )

        tool_events = []
        # Execute tool calls if any
        if sim_response.tool_calls:
            for tc in sim_response.tool_calls:
                event = await self._execute_tool(tc)
                tool_events.append(event)
            # Re-call LLM with tool results if needed (simple: append to text)
            tool_summary = "\n".join(
                f"[Tool {e['tool']}] {e.get('output', '')[:500]}" for e in tool_events
            )
            sim_response.text = f"{sim_response.text}\n\n{tool_summary}".strip()

        # Save AI turn
        ai_turn = SimulationTurn(
            session_id=session_id,
            seq=seq + 1,
            speaker="ai",
            modality="text",
            content=sim_response.text,
            time_offset_seconds=int(elapsed),
            tool_calls=[{"tool": tc.tool, "command": tc.command, "output": tc.output} for tc in sim_response.tool_calls],
        )
        self._db.add(ai_turn)
        await self._db.commit()

        session_complete = sim_response.end_signal or (time_remaining == 0)

        return {
            "response": sim_response.text,
            "tool_events": tool_events,
            "time_remaining_seconds": time_remaining,
            "session_complete": session_complete,
            "cutoff": False,
        }

    async def _execute_tool(self, tc) -> dict:
        """Execute a tool call. Minimal implementation — expand as needed."""
        try:
            if tc.tool == "terminal":
                from app.services.terminal_service import TerminalService
                svc = TerminalService()
                output = await asyncio.wait_for(svc.run(tc.command), timeout=15.0)
                return {"tool": "terminal", "command": tc.command, "output": str(output), "status": "done"}
            elif tc.tool == "code":
                # Simple Python eval via terminal
                from app.services.terminal_service import TerminalService
                svc = TerminalService()
                output = await asyncio.wait_for(svc.run(f"python -c \"{tc.command}\""), timeout=10.0)
                return {"tool": "code", "command": tc.command, "output": str(output), "status": "done"}
            elif tc.tool == "file":
                try:
                    with open(tc.command, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read(4096)
                    return {"tool": "file", "command": tc.command, "output": content, "status": "done"}
                except OSError as e:
                    return {"tool": "file", "command": tc.command, "output": str(e), "status": "error"}
        except Exception as e:
            return {"tool": tc.tool, "command": tc.command, "output": str(e), "status": "error"}
        return {"tool": tc.tool, "command": tc.command, "output": "unknown tool", "status": "error"}

    async def generate_debrief(self, session_id: str) -> dict:
        """Generate and persist debrief. Idempotent — returns cached if already done."""
        # Check if debrief already exists
        existing = await self._db.execute(
            select(SimulationDebrief).where(SimulationDebrief.session_id == session_id)
        )
        debrief = existing.scalar_one_or_none()
        if debrief:
            return self._debrief_to_dict(debrief)

        result = await self._db.execute(
            select(SimulationSession).where(SimulationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return {"error": "Session not found"}

        turns_result = await self._db.execute(
            select(SimulationTurn)
            .where(SimulationTurn.session_id == session_id)
            .order_by(SimulationTurn.seq)
        )
        turns = [
            {"speaker": t.speaker, "content": t.content, "time_offset_seconds": t.time_offset_seconds}
            for t in turns_result.scalars().all()
        ]

        brief = session.brief or {}
        result_data = await self._orchestrator.debrief(brief, turns, think=True)

        debrief = SimulationDebrief(
            id=str(uuid4()),
            session_id=session_id,
            scenario_type=session.scenario_type,
            overall_score=result_data.overall_score,
            hire_signal=result_data.hire_signal,
            core_scores=result_data.core_scores,
            scenario_scores=result_data.scenario_scores,
            summary=result_data.summary,
            strengths=result_data.strengths,
            improvements=result_data.improvements,
            focus_areas=result_data.focus_areas,
        )
        self._db.add(debrief)

        # Write UserProgress for core dimensions
        career_track = CAREER_TRACK_MAP.get(session.scenario_type or "custom", "technology")
        level = _detect_level(brief)
        for dimension, score in (result_data.core_scores or {}).items():
            progress = UserProgress(
                id=str(uuid4()),
                user_id=session.user_id,
                session_id=session_id,  # plain string — no FK after migration
                career_track=career_track,
                level=level,
                stage=session.scenario_type or "custom",
                skill_dimension=dimension,
                score=float(score),
            )
            self._db.add(progress)

        await self._db.commit()
        return self._debrief_to_dict(debrief)

    def _debrief_to_dict(self, d: SimulationDebrief) -> dict:
        return {
            "id": d.id,
            "session_id": d.session_id,
            "scenario_type": d.scenario_type,
            "overall_score": d.overall_score,
            "hire_signal": d.hire_signal,
            "core_scores": d.core_scores,
            "scenario_scores": d.scenario_scores,
            "summary": d.summary,
            "strengths": d.strengths or [],
            "improvements": d.improvements or [],
            "focus_areas": d.focus_areas or [],
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
```

- [ ] **Step 2: Verify imports**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.services.simulation_engine import SimulationEngine, _parse_time_budget; print(_parse_time_budget('90 seconds — hard cap'))"
```
Expected: `90`

- [ ] **Step 3: Quick unit check for parse_time_budget**
```bash
python -c "
from app.services.simulation_engine import _parse_time_budget
assert _parse_time_budget('90 seconds') == 90
assert _parse_time_budget('45 min') == 2700
assert _parse_time_budget('2 hours') == 7200
assert _parse_time_budget('Open-ended') is None
print('All assertions passed')
"
```

- [ ] **Step 4: Commit**
```bash
git add app/services/simulation_engine.py
git commit -m "feat(sim): SimulationEngine — session lifecycle, hard cutoff, debrief trigger"
```

---

## Task 7: SimDebriefService (PDF)

**Files:**
- Create: `backend/app/services/sim_debrief_service.py`

- [ ] **Step 1: Write the PDF service**

```python
# backend/app/services/sim_debrief_service.py
"""Generates a PDF report from a SimulationDebrief.
Uses the same reportlab pattern as the existing debrief_service.py if present;
falls back to a plain-text bytes response if reportlab is unavailable."""
import io

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    REPORTLAB = True
except ImportError:
    REPORTLAB = False


def generate_pdf(debrief: dict) -> bytes:
    """Return PDF bytes for a SimulationDebrief dict."""
    if not REPORTLAB:
        # Fallback: plain-text report as UTF-8 bytes
        lines = [
            f"Simulation Debrief Report",
            f"Session: {debrief.get('session_id', 'N/A')}",
            f"Scenario: {debrief.get('scenario_type', 'N/A')}",
            f"Overall Score: {debrief.get('overall_score', 'N/A')}/10",
            f"Hire Signal: {debrief.get('hire_signal', 'N/A')}",
            "",
            "Summary:",
            debrief.get("summary", ""),
            "",
            "Core Scores:",
        ]
        for k, v in (debrief.get("core_scores") or {}).items():
            lines.append(f"  {k}: {v}/10")
        lines.append("")
        lines.append("Scenario Scores:")
        for k, v in (debrief.get("scenario_scores") or {}).items():
            lines.append(f"  {k}: {v}/10")
        lines.append("")
        lines.append("Strengths:")
        for s in debrief.get("strengths", []):
            lines.append(f"  • {s}")
        lines.append("")
        lines.append("Areas to Improve:")
        for i in debrief.get("improvements", []):
            lines.append(f"  • {i}")
        lines.append("")
        lines.append("Focus Areas:")
        for f in debrief.get("focus_areas", []):
            lines.append(f"  → {f}")
        return "\n".join(lines).encode("utf-8")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Simulation Debrief Report", styles["Title"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Scenario: {debrief.get('scenario_type', 'N/A')}", styles["Normal"]))
    story.append(Paragraph(
        f"Overall Score: {debrief.get('overall_score', 'N/A')}/10 — {debrief.get('hire_signal', '')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.3*cm))

    if debrief.get("summary"):
        story.append(Paragraph("Summary", styles["Heading2"]))
        story.append(Paragraph(debrief["summary"], styles["Normal"]))
        story.append(Spacer(1, 0.3*cm))

    # Score table
    score_data = [["Dimension", "Score"]]
    for k, v in (debrief.get("core_scores") or {}).items():
        score_data.append([k.replace("_", " ").title(), f"{v}/10"])
    for k, v in (debrief.get("scenario_scores") or {}).items():
        score_data.append([k.replace("_", " ").title(), f"{v}/10"])

    if len(score_data) > 1:
        story.append(Paragraph("Scores", styles["Heading2"]))
        t = Table(score_data, colWidths=[10*cm, 4*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#050d18")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*cm))

    for heading, key in [("Strengths", "strengths"), ("Areas to Improve", "improvements"), ("Focus Areas", "focus_areas")]:
        items = debrief.get(key, [])
        if items:
            story.append(Paragraph(heading, styles["Heading2"]))
            for item in items:
                story.append(Paragraph(f"• {item}", styles["Normal"]))
            story.append(Spacer(1, 0.2*cm))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 2: Verify import**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.services.sim_debrief_service import generate_pdf; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add app/services/sim_debrief_service.py
git commit -m "feat(sim): PDF debrief report generator"
```

---

## Task 8: REST API + WebSocket Handler

**Files:**
- Create: `backend/app/api/v1/sim_sessions.py`

- [ ] **Step 1: Write the router**

```python
# backend/app/api/v1/sim_sessions.py
import asyncio
import base64
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import InvalidCredentialsError
from app.core import ws_registry
from app.models.pg.simulation import SimulationSession, SimulationDebrief
from app.schemas.simulation import CreateSimSessionRequest, SimTurnRequest
from app.services.simulation_engine import SimulationEngine
from app.services.sim_debrief_service import generate_pdf
from app.services.speech_service import SpeechService

router = APIRouter(prefix="/sim-sessions", tags=["simulation"])
logger = logging.getLogger(__name__)


async def _get_user_id(token: str) -> str:
    """Decode JWT and return user_id. Raises InvalidCredentialsError on failure."""
    return decode_token(token)


def _auth_header(authorization: str = Query(default=None, alias="authorization")) -> str | None:
    return authorization


# ── REST endpoints ──────────────────────────────────────────────────────────

@router.post("")
async def create_sim_session(
    body: CreateSimSessionRequest,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
):
    try:
        user_id = await _get_user_id(token or "")
    except (InvalidCredentialsError, Exception):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")

    engine = SimulationEngine(db)
    session_data = await engine.create_session(
        user_id=user_id,
        brief=body.brief,
        attachments=body.attachments,
    )
    return {"data": session_data, "error": None}


@router.get("/{session_id}")
async def get_sim_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
):
    from fastapi import HTTPException
    try:
        decode_token(token or "")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(SimulationSession).where(SimulationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"data": {
        "id": session.id,
        "scenario_type": session.scenario_type,
        "time_budget_seconds": session.time_budget_seconds,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "hard_cutoff_fired": session.hard_cutoff_fired,
        "persona": session.persona,
    }, "error": None}


@router.post("/{session_id}/end")
async def end_sim_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
):
    from fastapi import HTTPException
    from sqlalchemy import update
    from app.services.simulation_engine import utcnow
    try:
        decode_token(token or "")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    await db.execute(
        update(SimulationSession)
        .where(SimulationSession.id == session_id)
        .values(ended_at=utcnow())
    )
    await db.commit()

    engine = SimulationEngine(db)
    debrief = await engine.generate_debrief(session_id)
    return {"data": debrief, "error": None}


@router.post("/{session_id}/debrief")
async def trigger_debrief(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
):
    from fastapi import HTTPException
    try:
        decode_token(token or "")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    engine = SimulationEngine(db)
    debrief = await engine.generate_debrief(session_id)
    return {"data": debrief, "error": None}


@router.get("/{session_id}/debrief")
async def get_debrief(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
):
    from fastapi import HTTPException
    try:
        decode_token(token or "")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(SimulationDebrief).where(SimulationDebrief.session_id == session_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Debrief not yet generated")

    engine = SimulationEngine(db)
    return {"data": engine._debrief_to_dict(d), "error": None}


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
):
    from fastapi import HTTPException
    try:
        decode_token(token or "")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(SimulationDebrief).where(SimulationDebrief.session_id == session_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Debrief not yet generated")

    engine = SimulationEngine(db)
    pdf_bytes = generate_pdf(engine._debrief_to_dict(d))
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=simulation-report-{session_id[:8]}.pdf"
    })


# ── WebSocket ──────────────────────────────────────────────────────────────

async def _authenticate_ws(websocket: WebSocket, token: str | None) -> str | None:
    if not token:
        await websocket.close(code=4001)
        return None
    try:
        return decode_token(token)
    except (InvalidCredentialsError, Exception):
        await websocket.close(code=4001)
        return None


@router.websocket("/{session_id}/ws")
async def sim_session_ws(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    user_id = await _authenticate_ws(websocket, token)
    if user_id is None:
        return

    ws_registry.register(asyncio.current_task())
    await websocket.accept()

    # Fetch session metadata
    result = await db.execute(
        select(SimulationSession).where(SimulationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        await websocket.send_json({"type": "error", "code": "NOT_FOUND", "message": "Session not found"})
        await websocket.close()
        return

    engine = SimulationEngine(db)
    speech = SpeechService()
    budget = session.time_budget_seconds
    started_at = session.started_at

    # Timer task — ticks every second
    async def timer_loop():
        from app.services.simulation_engine import utcnow as _now
        from sqlalchemy import update
        try:
            while True:
                await asyncio.sleep(1)
                elapsed = (_now() - started_at).total_seconds()
                if budget:
                    remaining = max(0, int(budget - elapsed))
                    try:
                        await websocket.send_json({
                            "type": "timer_update",
                            "remaining_seconds": remaining,
                            "budget_seconds": budget,
                        })
                    except Exception:
                        break
                    if remaining == 0:
                        # Hard cutoff
                        cutoff_msgs = {
                            "pitch": "Time. Stop right there.",
                            "mr_review": "Time's up. Let's debrief.",
                            "system_design": "Time. Wrap it up.",
                            "teaching": "Class time is over.",
                            "behavioral": "Time. Thank you.",
                            "negotiation": "Time. We'll pause here.",
                        }
                        msg = cutoff_msgs.get(session.scenario_type or "custom", "Time.")
                        try:
                            await websocket.send_json({"type": "hard_cutoff", "message": msg})
                            await websocket.send_json({"type": "session_end", "reason": "time_expired"})
                        except Exception:
                            pass
                        await db.execute(
                            update(SimulationSession)
                            .where(SimulationSession.id == session_id)
                            .values(hard_cutoff_fired=True)
                        )
                        await db.commit()
                        break
        except asyncio.CancelledError:
            pass

    timer_task = asyncio.create_task(timer_loop())

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "ping":
                elapsed = int((session.started_at - session.started_at).total_seconds())
                await websocket.send_json({"type": "pong"})

            elif msg_type == "text_turn":
                content = msg.get("content", "")
                offset = msg.get("elapsed_seconds", 0)
                await websocket.send_json({
                    "type": "transcript", "speaker": "user", "text": content,
                    "seq": 0, "final": True,
                })
                turn_result = await engine.submit_turn(
                    session_id=session_id,
                    content=content,
                    modality="text",
                    time_offset_seconds=offset,
                )

                # Send tool events
                for te in turn_result.get("tool_events", []):
                    await websocket.send_json({"type": "tool_event", **te})

                ai_text = turn_result.get("response", "")
                await websocket.send_json({
                    "type": "transcript", "speaker": "ai", "text": ai_text,
                    "seq": 1, "final": True,
                })

                # Stream TTS
                try:
                    async for chunk in speech.synthesize_stream(ai_text):
                        await websocket.send_json({
                            "type": "ai_audio",
                            "data": base64.b64encode(chunk).decode(),
                        })
                except Exception as e:
                    logger.warning("[sim_ws] TTS error: %s", e)

                if turn_result.get("session_complete") or turn_result.get("cutoff"):
                    timer_task.cancel()
                    await websocket.send_json({
                        "type": "session_end",
                        "reason": "time_expired" if turn_result.get("cutoff") else "ai_ended",
                    })

            elif msg_type == "end_session":
                timer_task.cancel()
                await websocket.send_json({"type": "session_end", "reason": "user_ended"})
                break

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        timer_task.cancel()
        try:
            await timer_task
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 2: Verify import**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.api.v1.sim_sessions import router; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**
```bash
git add app/api/v1/sim_sessions.py
git commit -m "feat(sim): REST + WebSocket handler for simulation sessions"
```

---

## Task 9: Register Router in api/v1/__init__.py and main.py

**Files:**
- Modify: `backend/app/api/v1/__init__.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update api/v1/__init__.py**

`backend/app/api/v1/__init__.py` is currently a 1-line empty file. Add:
```python
from app.api.v1.sim_sessions import router as sim_sessions_router  # noqa: F401
```

- [ ] **Step 2: Add the import and include_router call in main.py**

In `main.py`, after the `cluely_sessions_router` import line, add:
```python
from app.api.v1.sim_sessions import router as sim_sessions_router
```

After `app.include_router(progress_router, prefix="/api/v1")`, add:
```python
app.include_router(sim_sessions_router, prefix="/api/v1")
```

- [ ] **Step 3: Verify startup**
```bash
cd backend
source venv/Scripts/activate
python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Verify route appears in docs**
```bash
uvicorn app.main:app --port 8001 --no-access-log &
sleep 2
curl http://localhost:8001/openapi.json | python -c "import sys,json; routes=[r for r in json.load(sys.stdin)['paths'].keys() if 'sim' in r]; print(routes)"
kill %1
```
Expected: list containing `/api/v1/sim-sessions`

- [ ] **Step 5: Commit**
```bash
git add app/api/v1/__init__.py app/main.py
git commit -m "feat(sim): register sim_sessions router in __init__.py and main.py"
```

---

## Task 10: Frontend — simulationStore

**Files:**
- Create: `frontend/src/store/simulationStore.ts`

- [ ] **Step 1: Write the store**

```typescript
// frontend/src/store/simulationStore.ts
import { create } from 'zustand'

interface SimulationState {
  activeSimSessionId: string | null
  persona: string
  timeBudgetSeconds: number | null
  scenarioType: string
  setSession: (
    sessionId: string,
    persona: string,
    timeBudgetSeconds: number | null,
    scenarioType: string
  ) => void
  clearSession: () => void
}

export const useSimulationStore = create<SimulationState>((set) => ({
  activeSimSessionId: null,
  persona: '',
  timeBudgetSeconds: null,
  scenarioType: '',
  setSession: (sessionId, persona, timeBudgetSeconds, scenarioType) =>
    set({ activeSimSessionId: sessionId, persona, timeBudgetSeconds, scenarioType }),
  clearSession: () =>
    set({ activeSimSessionId: null, persona: '', timeBudgetSeconds: null, scenarioType: '' }),
}))
```

- [ ] **Step 2: Verify TypeScript compiles**
```bash
cd frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors related to `simulationStore.ts`

- [ ] **Step 3: Commit**
```bash
git add src/store/simulationStore.ts
git commit -m "feat(sim): Zustand simulationStore"
```

---

## Task 11: Frontend — useSimulationSession Hook

**Files:**
- Create: `frontend/src/hooks/useSimulationSession.ts`

This hook centralises WebSocket lifecycle, timer management, and the voice pipeline so `SimulationSession.tsx` stays a pure rendering component.

- [ ] **Step 1: Write the hook**

```typescript
// frontend/src/hooks/useSimulationSession.ts
import { useEffect, useRef, useState, useCallback } from 'react'
import { useSimulationStore } from '../store/simulationStore'
import { useAuthStore } from '../store/authStore'

export interface SimTurn {
  id: string
  speaker: 'user' | 'ai'
  text: string
  toolEvents?: { tool: string; output: string; status: string }[]
}

export interface UseSimulationSession {
  turns: SimTurn[]
  remainingSeconds: number | null
  hardCutoff: boolean
  cutoffMessage: string
  sessionEnded: boolean
  sendText: (text: string) => void
  endSession: () => void
}

export function useSimulationSession(
  onDebrief: (data: any) => void,
): UseSimulationSession {
  const { activeSimSessionId, timeBudgetSeconds } = useSimulationStore()
  const token = useAuthStore((s) => s.accessToken)

  const [turns, setTurns] = useState<SimTurn[]>([])
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(timeBudgetSeconds)
  const [hardCutoff, setHardCutoff] = useState(false)
  const [cutoffMessage, setCutoffMessage] = useState('')
  const [sessionEnded, setSessionEnded] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const audioQueueRef = useRef<ArrayBuffer[]>([])
  const playingRef = useRef(false)

  const playNextChunk = useCallback(() => {
    if (playingRef.current || audioQueueRef.current.length === 0) return
    const buf = audioQueueRef.current.shift()!
    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext()
    audioCtxRef.current.decodeAudioData(buf).then((decoded) => {
      const src = audioCtxRef.current!.createBufferSource()
      src.buffer = decoded
      src.connect(audioCtxRef.current!.destination)
      playingRef.current = true
      src.onended = () => { playingRef.current = false; playNextChunk() }
      src.start()
    }).catch(() => { playingRef.current = false; playNextChunk() })
  }, [])

  useEffect(() => {
    if (!activeSimSessionId || !token) return
    const wsUrl = `ws://localhost:8000/api/v1/sim-sessions/${activeSimSessionId}/ws?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'transcript' && msg.final) {
        setTurns((prev) => [
          ...prev,
          { id: `${msg.speaker}-${Date.now()}`, speaker: msg.speaker, text: msg.text },
        ])
      }

      if (msg.type === 'timer_update') setRemainingSeconds(msg.remaining_seconds)

      if (msg.type === 'hard_cutoff') {
        setHardCutoff(true)
        setCutoffMessage(msg.message)
      }

      if (msg.type === 'tool_event') {
        setTurns((prev) => {
          if (prev.length === 0) return prev
          const last = { ...prev[prev.length - 1] }
          last.toolEvents = [...(last.toolEvents || []), msg]
          return [...prev.slice(0, -1), last]
        })
      }

      if (msg.type === 'session_end') {
        setSessionEnded(true)
        fetch(`/api/v1/sim-sessions/${activeSimSessionId}/debrief?token=${encodeURIComponent(token)}`, {
          method: 'POST',
        })
          .then((r) => r.json())
          .then((j) => { if (j.data) onDebrief(j.data) })
          .catch(() => {})
      }

      if (msg.type === 'ai_audio') {
        const bytes = Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0))
        audioQueueRef.current.push(bytes.buffer)
        playNextChunk()
      }
    }

    return () => { ws.close() }
  }, [activeSimSessionId, token, onDebrief, playNextChunk])

  const sendText = useCallback((text: string) => {
    if (!wsRef.current || !text.trim()) return
    wsRef.current.send(JSON.stringify({ type: 'text_turn', content: text, elapsed_seconds: 0 }))
  }, [])

  const endSession = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'end_session' }))
  }, [])

  return { turns, remainingSeconds, hardCutoff, cutoffMessage, sessionEnded, sendText, endSession }
}
```

- [ ] **Step 2: TypeScript compile check**
```bash
cd frontend
npx tsc --noEmit 2>&1 | grep "useSimulationSession" | head -10
```
Expected: no errors

- [ ] **Step 3: Commit**
```bash
git add src/hooks/useSimulationSession.ts
git commit -m "feat(sim): useSimulationSession hook — WS lifecycle, timer, audio queue"
```

---

## Task 12: Frontend — Wire SimulationBuilder.tsx

**Files:**
- Modify: `frontend/src/components/interview/SimulationBuilder.tsx`

- [ ] **Step 1: Read current file to find onLaunch and imports**

The file already has the full builder UI and accepts `onLaunch` prop conceptually. Find where the component is defined and where `onLaunch` should be called on launch.

Look for the `SimulationBuilder` component definition and the launch button / overlay "Enter Session" action.

- [ ] **Step 2: Add imports at top of SimulationBuilder.tsx**

Add after existing imports:
```typescript
import { useAuthStore } from '../../store/authStore'
import { useSimulationStore } from '../../store/simulationStore'
```

- [ ] **Step 3: Wire the launch action**

Inside the `SimulationBuilder` component, add:
```typescript
const token = useAuthStore((s) => s.accessToken)
const setSession = useSimulationStore((s) => s.setSession)
```

Replace the existing launch / "Enter Session" handler (the one called when the user clicks the final button in `LaunchOverlay`) with:
```typescript
const handleLaunch = async (params: { text: string; attachments: any[]; understood: any }) => {
  try {
    const res = await fetch('/api/v1/sim-sessions?token=' + encodeURIComponent(token ?? ''), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brief: params.understood, attachments: params.attachments }),
    })
    const json = await res.json()
    if (json.data?.session_id) {
      setSession(
        json.data.session_id,
        json.data.persona ?? '',
        json.data.time_budget_seconds ?? null,
        json.data.scenario_type ?? 'custom',
      )
    }
  } catch (e) {
    console.error('[SimulationBuilder] launch failed', e)
  }
}
```

Pass `handleLaunch` as the `onLaunch` prop where the inner builder calls it.

- [ ] **Step 4: TypeScript compile check**
```bash
cd frontend
npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 5: Commit**
```bash
git add src/components/interview/SimulationBuilder.tsx
git commit -m "feat(sim): wire SimulationBuilder onLaunch to POST /api/v1/sim-sessions"
```

---

## Task 13: Frontend — App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add import**

In `App.tsx`, add after the `useInterviewStore` import:
```typescript
import { useSimulationStore } from './store/simulationStore'
import SimulationSessionPage from './pages/SimulationSessionPage'
```

- [ ] **Step 2: Read the store in the component**

Inside `App()`, after the `sessionId` line, add:
```typescript
const activeSimSessionId = useSimulationStore((s) => s.activeSimSessionId)
```

- [ ] **Step 3: Add the render check**

After the `if (sessionId) return <InterviewSession .../>` line, add:
```typescript
if (activeSimSessionId) return <SimulationSessionPage />
```

- [ ] **Step 4: Compile check**
```bash
cd frontend
npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 5: Commit**
```bash
git add src/App.tsx
git commit -m "feat(sim): App.tsx renders SimulationSessionPage when activeSimSessionId is set"
```

---

## Task 14: Frontend — SimulationSession Component

**Files:**
- Create: `frontend/src/components/simulation/SimulationSession.tsx`

- [ ] **Step 1: Create the directory**
```bash
mkdir -p frontend/src/components/simulation
```

- [ ] **Step 2: Write SimulationSession.tsx**

```tsx
// frontend/src/components/simulation/SimulationSession.tsx
import { useEffect, useRef, useState } from 'react'
import { useSimulationStore } from '../../store/simulationStore'
import { useAuthStore } from '../../store/authStore'

interface Turn {
  id: string
  speaker: 'user' | 'ai'
  text: string
  toolEvents?: { tool: string; output: string; status: string }[]
}

interface Props {
  onDebrief: (debriefData: any) => void
  onEnd: () => void
}

export default function SimulationSession({ onDebrief, onEnd }: Props) {
  const { activeSimSessionId, timeBudgetSeconds, scenarioType } = useSimulationStore()
  const token = useAuthStore((s) => s.accessToken)
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [remaining, setRemaining] = useState<number | null>(timeBudgetSeconds)
  const [hardCutoff, setHardCutoff] = useState(false)
  const [cutoffMsg, setCutoffMsg] = useState('')
  const [sessionEnded, setSessionEnded] = useState(false)
  const transcriptRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)

  // Scroll transcript to bottom
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [turns])

  useEffect(() => {
    if (!activeSimSessionId || !token) return
    const wsUrl = `ws://localhost:8000/api/v1/sim-sessions/${activeSimSessionId}/ws?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'transcript') {
        if (!msg.final) return
        setTurns((prev) => [
          ...prev,
          { id: `${msg.speaker}-${Date.now()}`, speaker: msg.speaker, text: msg.text },
        ])
      }

      if (msg.type === 'timer_update') {
        setRemaining(msg.remaining_seconds)
      }

      if (msg.type === 'hard_cutoff') {
        setHardCutoff(true)
        setCutoffMsg(msg.message)
      }

      if (msg.type === 'tool_event') {
        setTurns((prev) => {
          const last = prev[prev.length - 1]
          if (!last) return prev
          return [
            ...prev.slice(0, -1),
            { ...last, toolEvents: [...(last.toolEvents || []), msg] },
          ]
        })
      }

      if (msg.type === 'session_end') {
        setSessionEnded(true)
        // Fetch debrief
        fetch(`/api/v1/sim-sessions/${activeSimSessionId}/debrief?token=${encodeURIComponent(token)}`, {
          method: 'POST',
        })
          .then((r) => r.json())
          .then((j) => {
            if (j.data) onDebrief(j.data)
          })
          .catch(() => {})
      }

      if (msg.type === 'ai_audio') {
        // Decode and play MP3 chunk
        const bytes = Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0))
        if (!audioCtxRef.current) {
          audioCtxRef.current = new AudioContext()
        }
        audioCtxRef.current.decodeAudioData(bytes.buffer).then((buf) => {
          const src = audioCtxRef.current!.createBufferSource()
          src.buffer = buf
          src.connect(audioCtxRef.current!.destination)
          src.start()
        }).catch(() => {})
      }
    }

    ws.onerror = () => {}
    ws.onclose = () => {}

    return () => { ws.close() }
  }, [activeSimSessionId, token])

  const sendText = () => {
    if (!input.trim() || !wsRef.current) return
    wsRef.current.send(JSON.stringify({ type: 'text_turn', content: input.trim(), elapsed_seconds: 0 }))
    setInput('')
  }

  const handleEnd = () => {
    wsRef.current?.send(JSON.stringify({ type: 'end_session' }))
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }

  const timerColor = remaining == null ? '#22d3ee'
    : remaining < 10 ? '#ef4444'
    : remaining < (timeBudgetSeconds ?? Infinity) * 0.2 ? '#f59e0b'
    : '#22d3ee'

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr auto 280px', height: '100%',
      background: '#070f1c', color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace',
      overflow: 'hidden',
    }}>
      {/* Left: Transcript */}
      <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(34,211,238,0.08)', overflow: 'hidden' }}>
        {hardCutoff && (
          <div style={{
            background: '#ef4444', color: '#fff', padding: '12px 20px',
            fontWeight: 700, fontSize: '15px', letterSpacing: '0.1em',
            textTransform: 'uppercase', textAlign: 'center',
          }}>
            TIME — {cutoffMsg}
          </div>
        )}
        <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {turns.map((t) => (
            <div key={t.id}>
              <div style={{ color: t.speaker === 'user' ? '#22d3ee' : '#9b7bff', fontSize: '12px', marginBottom: '4px', letterSpacing: '0.08em' }}>
                {t.speaker === 'user' ? 'YOU' : 'AI'}
              </div>
              <div style={{ fontSize: '14px', lineHeight: 1.6 }}>{t.text}</div>
              {t.toolEvents?.map((te, i) => (
                <div key={i} style={{
                  marginTop: '8px', background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)',
                  borderRadius: '4px', padding: '8px', fontSize: '12px', color: '#fbbf24',
                }}>
                  <div style={{ marginBottom: '4px' }}>[{te.tool}] {te.status}</div>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '11px' }}>{te.output}</pre>
                </div>
              ))}
            </div>
          ))}
        </div>
        {/* Input */}
        <div style={{ padding: '16px', borderTop: '1px solid rgba(34,211,238,0.08)', display: 'flex', gap: '8px' }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendText())}
            placeholder={sessionEnded ? 'Session ended' : 'Type your response...'}
            disabled={sessionEnded || hardCutoff}
            style={{
              flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(34,211,238,0.15)',
              borderRadius: '6px', padding: '10px 14px', color: '#e2e8f0', fontFamily: 'inherit',
              fontSize: '13px', outline: 'none',
            }}
          />
          <button
            onClick={sendText}
            disabled={sessionEnded || hardCutoff || !input.trim()}
            style={{
              padding: '10px 18px', background: 'rgba(34,211,238,0.12)', border: '1px solid rgba(34,211,238,0.3)',
              borderRadius: '6px', color: '#22d3ee', cursor: 'pointer', fontFamily: 'inherit', fontSize: '12px',
            }}
          >Send</button>
        </div>
      </div>

      {/* Center: Timer */}
      <div style={{
        width: '200px', display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', borderRight: '1px solid rgba(34,211,238,0.08)', padding: '0 20px',
      }}>
        {timeBudgetSeconds != null && (
          <>
            <div style={{
              fontSize: '48px', fontWeight: 700, color: timerColor,
              fontVariantNumeric: 'tabular-nums',
              animation: remaining != null && remaining < 10 ? 'pulse 1s infinite' : 'none',
            }}>
              {remaining != null ? formatTime(remaining) : formatTime(timeBudgetSeconds)}
            </div>
            <div style={{ fontSize: '10px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginTop: '8px' }}>
              {hardCutoff ? 'TIME' : 'REMAINING'}
            </div>
          </>
        )}
        {!sessionEnded && (
          <button
            onClick={handleEnd}
            style={{
              marginTop: '32px', padding: '8px 16px', background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#ef4444',
              cursor: 'pointer', fontFamily: 'inherit', fontSize: '11px', letterSpacing: '0.08em',
            }}
          >End Session</button>
        )}
      </div>

      {/* Right: Context panel */}
      <div style={{ padding: '20px', overflowY: 'auto', fontSize: '12px' }}>
        <div style={{ color: 'rgba(148,163,184,0.5)', letterSpacing: '0.1em', marginBottom: '12px' }}>SCENARIO</div>
        <div style={{ color: '#22d3ee', marginBottom: '20px' }}>{scenarioType}</div>
        <div style={{ color: 'rgba(148,163,184,0.5)', letterSpacing: '0.1em', marginBottom: '8px' }}>SESSION</div>
        <div style={{ color: 'rgba(148,163,184,0.6)' }}>{activeSimSessionId?.slice(0, 8)}</div>
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
    </div>
  )
}
```

- [ ] **Step 3: Compile check**
```bash
cd frontend
npx tsc --noEmit 2>&1 | grep "simulation" | head -20
```

- [ ] **Step 4: Commit**
```bash
git add src/components/simulation/SimulationSession.tsx
git commit -m "feat(sim): SimulationSession component — 3-zone layout, WS, hard cutoff banner"
```

---

## Task 15: Frontend — SimulationDebrief Component

**Files:**
- Create: `frontend/src/components/simulation/SimulationDebrief.tsx`

- [ ] **Step 1: Write SimulationDebrief.tsx**

```tsx
// frontend/src/components/simulation/SimulationDebrief.tsx
import { useSimulationStore } from '../../store/simulationStore'
import { useAuthStore } from '../../store/authStore'

interface Props {
  debrief: {
    overall_score: number
    hire_signal: string
    core_scores: Record<string, number>
    scenario_scores: Record<string, number>
    summary: string
    strengths: string[]
    improvements: string[]
    focus_areas: string[]
  }
  onDismiss: () => void
}

const HIRE_COLORS: Record<string, string> = {
  strong_yes: '#22c55e', yes: '#86efac', borderline: '#f59e0b',
  no: '#f87171', strong_no: '#ef4444',
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '12px' }}>
        <span style={{ color: 'rgba(226,232,240,0.8)' }}>{label.replace(/_/g, ' ')}</span>
        <span style={{ color: '#22d3ee', fontVariantNumeric: 'tabular-nums' }}>{score.toFixed(1)}</span>
      </div>
      <div style={{ height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px' }}>
        <div style={{
          height: '100%', borderRadius: '2px',
          width: `${(score / 10) * 100}%`,
          background: score >= 7 ? '#22d3ee' : score >= 5 ? '#f59e0b' : '#ef4444',
          transition: 'width 0.8s ease',
        }} />
      </div>
    </div>
  )
}

export default function SimulationDebrief({ debrief, onDismiss }: Props) {
  const { activeSimSessionId } = useSimulationStore()
  const token = useAuthStore((s) => s.accessToken)

  const downloadReport = () => {
    window.open(
      `/api/v1/sim-sessions/${activeSimSessionId}/report?token=${encodeURIComponent(token ?? '')}`,
      '_blank'
    )
  }

  const hireColor = HIRE_COLORS[debrief.hire_signal] ?? '#94a3b8'

  return (
    <div style={{
      height: '100%', overflowY: 'auto', padding: '32px 40px',
      background: '#070f1c', color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px', marginBottom: '32px' }}>
        <div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '6px' }}>
            OVERALL SCORE
          </div>
          <div style={{ fontSize: '56px', fontWeight: 700, color: '#22d3ee', lineHeight: 1 }}>
            {debrief.overall_score.toFixed(1)}
          </div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.4)', marginTop: '4px' }}>out of 10</div>
        </div>
        <div style={{
          padding: '8px 20px', borderRadius: '20px', border: `1px solid ${hireColor}`,
          color: hireColor, fontSize: '13px', fontWeight: 600, letterSpacing: '0.08em',
          background: `${hireColor}15`,
        }}>
          {debrief.hire_signal.replace(/_/g, ' ').toUpperCase()}
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={downloadReport} style={{
          padding: '10px 20px', background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.25)',
          borderRadius: '6px', color: '#22d3ee', cursor: 'pointer', fontFamily: 'inherit',
          fontSize: '11px', letterSpacing: '0.1em',
        }}>↓ DOWNLOAD PDF</button>
        <button onClick={onDismiss} style={{
          padding: '10px 20px', background: 'rgba(148,163,184,0.06)', border: '1px solid rgba(148,163,184,0.15)',
          borderRadius: '6px', color: 'rgba(148,163,184,0.7)', cursor: 'pointer', fontFamily: 'inherit',
          fontSize: '11px', letterSpacing: '0.1em',
        }}>← BACK</button>
      </div>

      {/* Summary */}
      {debrief.summary && (
        <div style={{
          padding: '16px 20px', background: 'rgba(34,211,238,0.04)',
          border: '1px solid rgba(34,211,238,0.1)', borderRadius: '8px', marginBottom: '28px',
          fontSize: '14px', lineHeight: 1.7, color: 'rgba(226,232,240,0.85)',
        }}>{debrief.summary}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '28px', marginBottom: '28px' }}>
        {/* Core scores */}
        <div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '14px' }}>
            CORE DIMENSIONS
          </div>
          {Object.entries(debrief.core_scores || {}).map(([k, v]) => (
            <ScoreBar key={k} label={k} score={v} />
          ))}
        </div>
        {/* Scenario scores */}
        {Object.keys(debrief.scenario_scores || {}).length > 0 && (
          <div>
            <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '14px' }}>
              SCENARIO DIMENSIONS
            </div>
            {Object.entries(debrief.scenario_scores || {}).map(([k, v]) => (
              <ScoreBar key={k} label={k} score={v} />
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '28px' }}>
        {/* Strengths */}
        <div>
          <div style={{ fontSize: '11px', color: '#22c55e', letterSpacing: '0.12em', marginBottom: '12px' }}>
            STRENGTHS
          </div>
          {debrief.strengths.map((s, i) => (
            <div key={i} style={{ fontSize: '13px', marginBottom: '8px', paddingLeft: '12px', borderLeft: '2px solid rgba(34,197,94,0.4)' }}>
              {s}
            </div>
          ))}
        </div>
        {/* Improvements */}
        <div>
          <div style={{ fontSize: '11px', color: '#f59e0b', letterSpacing: '0.12em', marginBottom: '12px' }}>
            IMPROVE
          </div>
          {debrief.improvements.map((s, i) => (
            <div key={i} style={{ fontSize: '13px', marginBottom: '8px', paddingLeft: '12px', borderLeft: '2px solid rgba(245,158,11,0.4)' }}>
              {s}
            </div>
          ))}
        </div>
      </div>

      {/* Focus areas */}
      {debrief.focus_areas?.length > 0 && (
        <div>
          <div style={{ fontSize: '11px', color: 'rgba(148,163,184,0.5)', letterSpacing: '0.12em', marginBottom: '12px' }}>
            TOP FOCUS AREAS
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {debrief.focus_areas.map((f, i) => (
              <div key={i} style={{
                padding: '8px 16px', background: 'rgba(155,123,255,0.1)',
                border: '1px solid rgba(155,123,255,0.25)', borderRadius: '20px',
                color: '#9b7bff', fontSize: '12px',
              }}>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Compile check**
```bash
cd frontend
npx tsc --noEmit 2>&1 | grep "SimulationDebrief" | head -10
```

- [ ] **Step 3: Commit**
```bash
git add src/components/simulation/SimulationDebrief.tsx
git commit -m "feat(sim): SimulationDebrief component — scores, bars, strengths, PDF download"
```

---

## Task 16: Frontend — SimulationSessionPage

**Files:**
- Create: `frontend/src/pages/SimulationSessionPage.tsx`

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/SimulationSessionPage.tsx
import { useState } from 'react'
import { useSimulationStore } from '../store/simulationStore'
import SimulationSession from '../components/simulation/SimulationSession'
import SimulationDebrief from '../components/simulation/SimulationDebrief'

type Phase = 'session' | 'debrief'

export default function SimulationSessionPage() {
  const clearSession = useSimulationStore((s) => s.clearSession)
  const [phase, setPhase] = useState<Phase>('session')
  const [debriefData, setDebriefData] = useState<any>(null)

  const handleDebrief = (data: any) => {
    setDebriefData(data)
    setPhase('debrief')
  }

  const handleDismiss = () => {
    clearSession()
  }

  return (
    <div style={{ height: '100vh', overflow: 'hidden', background: '#070f1c' }}>
      {phase === 'session' ? (
        <SimulationSession
          onDebrief={handleDebrief}
          onEnd={clearSession}
        />
      ) : debriefData ? (
        <SimulationDebrief
          debrief={debriefData}
          onDismiss={handleDismiss}
        />
      ) : null}
    </div>
  )
}
```

- [ ] **Step 2: Full TypeScript compile check**
```bash
cd frontend
npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors (or pre-existing errors unrelated to simulation files)

- [ ] **Step 3: Commit**
```bash
git add src/pages/SimulationSessionPage.tsx
git commit -m "feat(sim): SimulationSessionPage — session → debrief state machine"
```

---

## Task 17: Integration Smoke Test

At this point all files are in place. Run a full integration check.

- [ ] **Step 1: Start the backend**
```bash
cd backend
source venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```
Expected: server starts, no import errors, `/api/v1/sim-sessions` visible in logs

- [ ] **Step 2: Start the frontend**
```bash
cd frontend
npm run dev
```
Expected: Vite compiles without TypeScript errors

- [ ] **Step 3: Manual smoke test flow**
1. Open the app in Electron or browser at `localhost:5173`
2. Log in with a test account
3. Navigate to Interview Prep — Simulation Builder loads
4. Type a scenario like "90-second product pitch, I'll pitch you on Notion"
5. Click Launch — builder should POST to `/api/v1/sim-sessions` and navigate to SimulationSessionPage
6. Type a response in the text input — AI should reply
7. Timer should count down (if time budget was parsed)
8. Click "End Session" — debrief screen should appear

- [ ] **Step 4: Final commit**
```bash
cd ..
git add -A
git commit -m "feat(sim): universal simulation engine — full integration (backend + frontend)"
```

---

## Appendix: Constraint Checks

| Risk | Mitigation |
|------|-----------|
| `UserProgress.session_id` FK violation | Migration drops FK; column stays as plain String |
| Timer drift on slow LLM calls | Timer runs in separate asyncio task; hard cutoff is a server-side elapsed check, not client-dependent |
| `synthesize_stream` not available in older openai SDK | Requires `openai>=1.14.0` — check `pip show openai` |
| WS auth fails silently | Close 4001 before `accept()` — same pattern as existing `_authenticate_ws` |
| Missing `JetBrains Mono` font in SimulationSession | Font already loaded globally via SimulationBuilder.css; no additional import needed |
| Alembic constraint name differs | Migration wraps `drop_constraint` in try/except; check actual name in `pg_constraint` if it fails |
