# Universal Simulation Engine — Design Spec
**Date:** 2026-05-30  
**Status:** Approved  
**Approach:** B — New `SimulationSession` layer (clean separation from existing interview engine)

---

## Overview

A universal, voice-first simulation engine that can rehearse any scenario — pitch practice, MR review + live pairing, system design, teaching sessions, behavioral panels, or anything the user describes. The Simulation Builder (already built) collects and interprets context; this spec covers wiring it to the backend and building the live session experience.

Key principles:
- **Robust, not hardcoded** — no assumptions about scenario type. Everything flows from the `brief` JSONB.
- **Voice first** — user speaks, AI speaks back. Text is a fallback.
- **Hard time enforcement** — when the clock hits zero the AI cuts the user off, no exceptions, mid-sentence.
- **Real file/code context** — attachments are pre-analyzed silently; AI plays discovery live but is grounded in actual analysis.
- **Dynamic debrief** — fixed core dimensions + scenario-specific dimensions the AI derives per simulation.

---

## Section 1 — Data Model

### New Tables (no changes to existing interview tables)

#### SQLAlchemy conventions used in this project
- `user_id` is stored as `String` (not VARCHAR) with `ForeignKey("users.id")`
- Array-valued columns use `JSONB` with `default=list` — NOT PostgreSQL `ARRAY(JSONB)` — matching the existing pattern on `work_experience`, `skills`, etc.
- All `JSONB[]` below means `Column(JSONB, default=list)` in SQLAlchemy
- All models use the `Mapped[type] = mapped_column(...)` style from SQLAlchemy 2.x. The pseudo-notation in this spec is shorthand — follow `session.py` as the reference template when writing the ORM models.

#### `SimulationSession`
```python
# SQLAlchemy ORM (follows existing model conventions)
id                    String, primary_key=True, default=uuid4
user_id               String, ForeignKey("users.id"), nullable=False
scenario_type         String(50)   # pitch | mr_review | system_design | teaching | behavioral | negotiation | custom
                                   # Derived via SCENARIO_TYPE_MAP (see Section 2)
brief                 JSONB        # full UnderstoodState: {confident, summaryParts, fields[]}
                                   # fields include: Scenario, You play, I'll play, Format,
                                   #                 Time, Materials, Pressure, I'll push on
attachments           JSONB, default=list   # [{kind, name, meta, content_preview, full_path, analysis}]
time_budget_seconds   Integer, nullable     # parsed from brief.fields[Time]; None = open-ended
started_at            DateTime, default=utcnow
ended_at              DateTime, nullable
hard_cutoff_fired     Boolean, default=False
persona               Text         # AI character built at session create
```

#### `SimulationTurn`
```python
id                    String, primary_key=True, default=uuid4
session_id            String, ForeignKey("simulation_sessions.id"), nullable=False
seq                   Integer              # ordering within session
speaker               String(10)           # "user" | "ai"
modality              String(10)           # "voice" | "text"
content               Text                 # transcript of this turn
audio_url             String(512), nullable
time_offset_seconds   Integer              # seconds from session.started_at
tool_calls            JSONB, default=list  # [{type, command, output, duration_ms}]
emotion_state         String(50), nullable
rewrite_count         Integer, default=0
```

#### `SimulationDebrief`
```python
id                    String, primary_key=True, default=uuid4
session_id            String, ForeignKey("simulation_sessions.id"), nullable=False
scenario_type         String(50)
overall_score         Float
hire_signal           String(20)           # strong_yes | yes | borderline | no | strong_no
core_scores           JSONB                # {communication, time_management, pressure_handling,
                                           #  structure, depth} each 0-10 (always present)
scenario_scores       JSONB                # AI-derived per scenario, e.g.:
                                           #   pitch:    {hook_clarity, defensibility, handling_pushback}
                                           #   mr_review: {code_reasoning, tradeoff_articulation, ...}
                                           #   teaching:  {explanation_quality, handling_confusion, ...}
summary               Text
strengths             JSONB, default=list
improvements          JSONB, default=list
focus_areas           JSONB, default=list  # top 3
created_at            DateTime, default=utcnow
```

---

## Section 2 — SimulationEngine Service

**File:** `backend/app/services/simulation_engine.py`

### Time Parsing
```python
def parse_time_budget(time_str: str) -> int | None:
    # "90 seconds — hard cap" → 90
    # "~45 minutes" → 2700
    # "2 hours" → 7200
    # "Open-ended" → None
```

### Scenario Type Mapping
`scenario_type` is derived from `brief.fields["Format"]` via a lookup table (no fuzzy LLM call):
```python
SCENARIO_TYPE_MAP = [
    (re.compile(r"pitch|elevator|verbal pitch", re.I),         "pitch"),
    (re.compile(r"mr review|merge request|code review", re.I), "mr_review"),
    (re.compile(r"system design|architecture", re.I),          "system_design"),
    (re.compile(r"teach|lesson|class|student", re.I),          "teaching"),
    (re.compile(r"behavioral|star|panel", re.I),               "behavioral"),
    (re.compile(r"pair.program|live cod", re.I),               "mr_review"),
    (re.compile(r"negotiat|sales", re.I),                      "negotiation"),
]
# Fallback: "custom" if no rule matches
```
Allowed `scenario_type` values: `pitch | mr_review | system_design | teaching | behavioral | negotiation | custom`

### `create_session(user_id, brief, attachments) → dict`
1. Parse `brief.fields[Time]` → `time_budget_seconds`
2. Detect `scenario_type` via `SCENARIO_TYPE_MAP` applied to `brief.fields["Format"]`
3. Pre-load attachments via `FileService.read_file()` / `CodeRunner.execute()`:
   - Files: read content, store in Redis under `sim:{session_id}:attachments` with TTL = `SESSION_TTL` (4 hours, the existing constant in `cache.py`)
   - Code/MR: run silently, capture errors, store analysis result under same key + TTL
   - AI pre-knows what's broken; will simulate discovering it live
4. `SimLLMOrchestrator.build_sim_persona(brief)` → persona string
5. Create `SimulationSession` row in PostgreSQL
6. Return `{session_id, persona, time_budget_seconds, scenario_type}`

### `submit_turn(session_id, content, modality, time_offset_seconds) → dict`
1. Fetch session; compute `elapsed = now - started_at`
2. **Hard cutoff check**: if `elapsed >= time_budget_seconds` (and budget is not None):
   - Set `hard_cutoff_fired = True`, `ended_at = now`
   - Return `{cutoff: true, response: "[HARD STOP]", session_complete: true}`
   - No LLM call, no exceptions
3. Build rolling context:
   - Last 20 `SimulationTurn`s
   - `attachment_context` from Redis
   - Full `brief`
   - `time_remaining_pct = 1 - (elapsed / budget)`
4. Call `SimLLMOrchestrator.respond(brief, turns, content, attachment_context, time_remaining_pct)`
5. If LLM response contains `tool_calls`:
   - Execute via `TerminalService` / `CodeRunner` / `FileService`
   - Append tool results to response context; re-call LLM for final text
6. Save `SimulationTurn` (both user turn and AI turn)
7. Return `{response, tool_events[], time_remaining_seconds, session_complete}`

### Hard Cutoff Mechanics
- Timer tracked server-side from `session.started_at`
- WebSocket server pings timer every second
- At `time_remaining <= 0`:
  - Any in-flight LLM stream is killed immediately
  - `hard_cutoff` event emitted to client
  - AI cutoff message injected: based on scenario (e.g. "Time. Stop right there." for pitch)
  - `session_end` event fires
  - Next client message auto-triggers debrief

### `generate_debrief(session_id) → dict`
1. Fetch all `SimulationTurn`s ordered by `seq`
2. Build full transcript with timing metadata
3. Call `SimLLMOrchestrator.debrief(brief, turns, think=True)` (DeepSeek-R1)
4. LLM returns: core scores + scenario-specific dimensions + summary + strengths + improvements
5. Persist `SimulationDebrief`
6. Write `UserProgress` records for core dimensions:
   - **FK resolution**: `UserProgress.session_id` has a hard FK to `sessions.id` (the `InterviewSession` table). `SimulationSession` IDs are not in that table and will cause a FK violation at runtime. Resolution: drop the FK constraint on `UserProgress.session_id` in a new migration, leaving it as a plain `String` (logical-only link — matching the `cluely_sessions.application_id` pattern). Add this migration to `XXXX_add_simulation_tables.py`.
   - `career_track`: derived from `scenario_type` → e.g. `pitch → "sales_marketing"`, `mr_review|system_design → "technology"`, `teaching → "education_training"`, default `"technology"`
   - `level`: extracted from `brief.fields["I'll play"]` — if "junior/entry/intern" → "entry_level", "senior/staff/principal" → "senior", else → "mid_level"
   - `stage`: set to `session.scenario_type`
7. Return debrief dict

---

## Section 3 — SimLLMOrchestrator

**File:** `backend/app/services/sim_llm_orchestrator.py`

Parallel to `LLMOrchestrator` but prompt-schema is scenario-agnostic. All prompts embed the full `brief` rather than hardcoded `company/role/round_type`.

### Key Methods

**`build_sim_persona(brief) → str`**
- Generates the AI character from `brief.fields["I'll play"]` + `brief.fields["Pressure"]`
- 2-3 sentences, concrete personality, no fluff

**`respond(brief, turns, user_content, attachment_context, time_remaining_pct) → SimResponse`**
```python
SimResponse:
    text: str                    # AI spoken response
    tool_calls: list[ToolCall]   # optional: terminal/code/file actions
    end_signal: bool             # AI decides session is complete (e.g. pitch Q&A done)
```
- Prompt embeds: persona, scenario format, pressure tone, focus areas, time pressure signal, full attachment analysis, conversation history
- Time pressure: if `time_remaining_pct < 0.15` → AI becomes more urgent/cutting
- Attachment-aware: if MR attached, AI can reference specific lines, ask "why did you choose this approach on line 42"
- Tool calls: AI can emit `{"tool": "terminal", "command": "python test.py"}` → engine executes → result fed back

**`debrief(brief, turns, think=True) → DebriefResult`**
- One-shot reasoning call (DeepSeek-R1)
- Returns structured JSON:
```json
{
  "overall_score": 7.2,
  "hire_signal": "yes",
  "core_scores": {
    "communication": 8.1,
    "time_management": 6.0,
    "pressure_handling": 7.5,
    "structure": 7.8,
    "depth": 6.9
  },
  "scenario_scores": {
    "hook_clarity": 7.0,
    "defensibility": 6.5,
    "handling_pushback": 8.0
  },
  "summary": "...",
  "strengths": [...],
  "improvements": [...],
  "focus_areas": [...]
}
```
- Scenario dimensions inferred from `brief.fields["Format"]` — no hardcoding

---

## Section 4 — API & WebSocket

### REST Endpoints

```
POST  /api/v1/sim-sessions
      Body: {brief, attachments[]}
      Returns: {session_id, persona, time_budget_seconds, scenario_type}

GET   /api/v1/sim-sessions/{id}
      Returns: session + turns[]

POST  /api/v1/sim-sessions/{id}/end
      Ends session early; generates debrief as side effect; returns debrief dict

POST  /api/v1/sim-sessions/{id}/debrief
      Explicit debrief trigger (idempotent — returns cached if already generated)

GET   /api/v1/sim-sessions/{id}/debrief
      Returns persisted debrief only; 404 if not yet generated (no write side-effects)

GET   /api/v1/sim-sessions/{id}/report
      Returns PDF bytes — generates from SimulationDebrief, adapted from debrief_service.py
      (backend/app/services/sim_debrief_service.py — new file, see file list)
```

### Pydantic Schemas
All request/response shapes defined in `backend/app/schemas/simulation.py` (new file):
- `CreateSimSessionRequest` — `{brief: dict, attachments: list[dict]}`
- `SimTurnRequest` — `{content: str, modality: str, time_offset_seconds: int}`
- `SimDebriefResponse` — full debrief dict shape
- `SimSessionResponse` — session + turns[]

### WebSocket Authentication
WS endpoint uses the same pattern as all existing WS endpoints in the codebase:
- `?token=<JWT>` query parameter
- Authenticated via shared `_authenticate_ws(token)` helper (`api/v1/ws.py`)
- On failure: close with code `4001` ("Unauthorized")
- Example: `ws://localhost:8000/api/v1/sim-sessions/{id}/ws?token=<jwt>`

### WebSocket: `/api/v1/sim-sessions/{id}/ws`

**Client → Server:**
```json
{"type": "audio_frame",   "data": "<base64 PCM>"}
{"type": "text_turn",     "content": "..."}
{"type": "ping",          "elapsed_seconds": 42}
{"type": "end_session"}
```

**Server → Client:**
```json
{"type": "transcript",    "speaker": "user|ai", "text": "...", "seq": 1, "final": true}
{"type": "ai_audio",      "data": "<base64 MP3 chunk>"}
{"type": "tool_event",    "tool": "terminal|code|file", "status": "running|done", "output": "..."}
{"type": "timer_update",  "remaining_seconds": 47, "budget_seconds": 90}
{"type": "hard_cutoff",   "message": "Time. Stop right there."}
{"type": "session_end",   "reason": "time_expired|user_ended|ai_ended"}
{"type": "error",         "code": "...", "message": "..."}
```

### Voice Pipeline (per turn)
1. Client streams PCM → `AudioService` buffers
2. Silence detection → Deepgram transcription → user `SimulationTurn`
3. `SimulationEngine.submit_turn()` → LLM response
4. TTS: `speech_service.py` must be updated to use OpenAI's streaming response (`with_streaming_response.audio.speech.create()`) and yield MP3 chunks rather than blocking on the full blob. The WS handler iterates chunks, sending each as an `ai_audio` event.
   - `speech_service.py` is added to the Backend (modify) file list for this reason.
5. Timer ticks every second; at 0 → `hard_cutoff` + kill any in-flight LLM stream

---

## Section 5 — Frontend Changes

### Modified: `SimulationBuilder.tsx`
- `onLaunch` calls `POST /api/v1/sim-sessions` with `{brief, attachments}`
- On success: navigate to `/simulation/{session_id}`

### New: `SimulationSession.tsx`
Three-zone layout (matches existing dark cyber aesthetic from the builder):

**Left — Transcript**
- User turns: cyan text
- AI turns: violet text  
- Tool events: amber, monospace output block
- On `hard_cutoff`: full-width red banner slams in — `"TIME — {cutoff message}"`
- Auto-scrolls

**Center — Timer**
- Hidden if `time_budget_seconds` is null (open-ended)
- Full size countdown: `MM:SS`
- Turns amber at < 20% remaining
- Turns red + pulses at < 10s remaining
- At 0: freezes, red, `"TIME"`

**Right — Context Panel**
- Attachments list with status (analyzed / running / error)
- Tool output feed (terminal stdout, code results)
- Detected signals from builder brief
- Mute button + mic activity indicator (waveform bars)
- Text fallback input (collapsed by default, toggle to expand)

### New: `SimulationDebrief.tsx`
- Overall score (large, prominent) + hire signal badge
- Core dimensions: always 5, horizontal bar chart
- Scenario dimensions: AI-derived, same bar chart below
- Transcript replay: full conversation with timing. Turn-level annotations are NOT included in this iteration (no `ai_internal_note` field in `SimulationTurn`; descoped).
- Download PDF button → `GET /api/v1/sim-sessions/{id}/report`

### Navigation — No React Router
The app uses a `useState<Screen>` state machine in `App.tsx` — there is no React Router. Navigation to the simulation session follows the same pattern as `InterviewSession`:
- `simulationStore.ts` holds `activeSimSessionId: string | null`
- `App.tsx` reads `activeSimSessionId`; if set, renders `SimulationSessionPage` instead of `Dashboard`
- `SimulationBuilder.onLaunch` calls `POST /api/v1/sim-sessions`, then calls `simulationStore.setSession(session_id, ...)`
- On session end / debrief dismissed: `simulationStore.clearSession()` → back to Dashboard

### `App.tsx`
- Add `useSimulationStore` check: if `activeSimSessionId` is set, render `SimulationSessionPage`
- No router changes needed

---

## Capability Matrix

| Scenario | Time Enforcement | File/Code Context | Tool Calls | Debrief Dimensions |
|----------|-----------------|-------------------|------------|-------------------|
| 90-sec Pitch | Hard cutoff at 90s | N/A | None | hook_clarity, defensibility, handling_pushback |
| MR Review + Pairing | Optional (e.g. 45 min) | MR diff pre-analyzed, run live | terminal, code | code_reasoning, tradeoff_articulation, communication_under_review |
| System Design | Optional (45 min) | Diagrams/docs if attached | file | scoping, tradeoffs, bottlenecks, failure_modes |
| Teaching Session | Optional | Slides/docs if attached | None | explanation_quality, handling_confusion, engagement, pacing |
| Behavioral Panel | Optional | None | None | specificity, ownership, measurable_outcomes, handling_pressure |
| Negotiation/Sales | Optional | None | None | clarity_of_position, handling_objections, closing_strength |
| Custom | As described | Whatever attached | As needed | AI-derived from brief |

---

## What Is Not In Scope (This Iteration)

- Multiplayer / group simulations
- Branching scenario trees (rewind and try again)
- Video avatar for the AI character (Simli integration — future)
- Mobile client
- Recording/playback of session audio

---

## Files To Create / Modify

**Backend (new):**
- `backend/app/models/pg/simulation.py` — 3 new SQLAlchemy models
- `backend/app/schemas/simulation.py` — Pydantic request/response schemas
- `backend/app/services/simulation_engine.py` — session lifecycle + hard cutoff
- `backend/app/services/sim_llm_orchestrator.py` — scenario-agnostic prompts
- `backend/app/services/sim_debrief_service.py` — debrief + PDF generation
- `backend/app/api/v1/sim_sessions.py` — REST endpoints + WS handler
- `backend/alembic/versions/XXXX_add_simulation_tables.py` — migration

**Backend (modify):**
- `backend/app/api/v1/__init__.py` — register `sim_sessions` router
- `backend/app/main.py` — mount WS route for sim sessions
- `backend/app/services/speech_service.py` — add streaming TTS method (`synthesize_stream`) using `with_streaming_response.audio.speech.create()`

**Frontend (new):**
- `frontend/src/pages/SimulationSessionPage.tsx`
- `frontend/src/components/simulation/SimulationSession.tsx`
- `frontend/src/components/simulation/SimulationDebrief.tsx`
- `frontend/src/hooks/useSimulationSession.ts`
- `frontend/src/store/simulationStore.ts`

**Frontend (modify):**
- `frontend/src/components/interview/SimulationBuilder.tsx` — wire `onLaunch` to POST + store
- `frontend/src/App.tsx` — add `useSimulationStore` check to render `SimulationSessionPage`
