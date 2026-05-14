# Realistic Interview Engine Design

## Goal

Transform the interview session from a static 5-question graded quiz into a dynamic evaluation that mirrors a real interview: tracks response timing and hesitation, detects factual errors, generates targeted follow-up questions, enforces time budgets per round type, and produces a holistic hire/no-hire recommendation — not just an average score.

## Architecture

Four layers of change:

1. **Data** — new columns on `Round` and `RoundMoment` to capture behavioral signals
2. **Backend** — upgraded grading, new follow-up logic, new holistic evaluation, behavioral signal endpoint
3. **Frontend** — timer tracking, rewrite detection, follow-up display, time warning banner, avatar reactions
4. **LLM prompts** — brutally honest persona, factual accuracy check, confidence scoring, holistic evaluation

---

## Section 1: Data Model

### `RoundMoment` (new columns)

| Column | Type | Description |
|---|---|---|
| `time_taken_seconds` | `Integer`, nullable | Seconds from question display to submit click |
| `rewrite_count` | `Integer`, default 0 | Number of times ≥40 chars were deleted in one edit |
| `is_followup` | `Boolean`, default false | True if this moment is a follow-up, not a prepared question |

### `Round` (new columns)

| Column | Type | Description |
|---|---|---|
| `started_at` | `DateTime`, default utcnow | Set when the round is created |
| `time_budget_seconds` | `Integer`, nullable | Max allowed seconds for this round type |

### Time budgets (server-side constants in `interview_engine.py`)

```python
ROUND_TIME_BUDGETS = {
    "behavioral": 1800,
    "hr_interview": 1800,
    "hr": 1800,
    "hiring_manager": 2400,
    "technical": 3600,
    "skills_domain": 3600,
    "panel_interview": 3600,
    "case_presentation": 3600,
    "final_executive": 2400,
    "offer_negotiation": 1800,
    "leetcode": 5400,
}
DEFAULT_TIME_BUDGET = 1800
```

### Alembic migration

One migration: `add_behavioral_signal_columns` — adds all five new columns across two tables.

---

## Section 2: Backend Changes

### `LLMOrchestrator`

#### `grade_answer` — upgraded

New signature:
```python
async def grade_answer(
    self, question: str, answer: str, company: str, role: str, round_type: str,
    time_taken_seconds: int | None = None,
    rewrite_count: int = 0,
) -> dict
```

Timing classification (derived before prompt construction):
- `< 10s` → "answered suspiciously fast — likely insufficient depth"
- `10–120s` → normal, no note
- `120–180s` → "slow response, possible hesitation"
- `> 180s` → "significantly over time, affects confidence assessment"

Rewrite classification:
- `0` → no note
- `1` → "rewrote answer once — minor hesitation"
- `2+` → "rewrote answer {n} times — candidate appears uncertain"

Prompt persona:
> "You are a senior interviewer at {company}. You are direct, fair, and brutally honest. You do not inflate scores. A score of 7 means genuinely good. A score of 5 means mediocre. A score of 3 means poor. You check factual accuracy — if the candidate says something demonstrably false, you note it and it lowers the score significantly."

Return schema:
```json
{
  "score": 6.5,
  "passed": true,
  "what_worked": "One clear sentence.",
  "what_was_missing": "One clear sentence.",
  "stronger_version": "One sentence showing improvement.",
  "follow_up": "Follow-up question if score < 7 and gap exists, else null",
  "factual_errors": ["List of factual errors found, empty if none"],
  "confidence_signal": "confident | hesitant | uncertain | rushed"
}
```

Pass threshold: score >= 5 (down from 6 — follow-ups compensate for initial weak answers).
Fail threshold: score <= 3 (immediate round fail, unchanged).

#### `evaluate_candidate` — new method

Called once when a round closes (last question answered or time expired). Receives the full round transcript including follow-ups, timing data per moment, and rewrite counts.

```python
async def evaluate_candidate(
    self,
    company: str,
    role: str,
    round_type: str,
    moments: list[dict],  # {question, answer, score, time_taken_seconds, rewrite_count, is_followup}
    time_budget_seconds: int,
    actual_duration_seconds: int,
) -> dict
```

Returns:
```json
{
  "hire_recommendation": "strong_yes | yes | borderline | no | strong_no",
  "confidence_rating": "high | medium | low | erratic",
  "overall_score": 7.2,
  "summary": "Two honest sentences about the candidate.",
  "strengths": ["..."],
  "concerns": ["..."],
  "time_management": "efficient | adequate | slow | over_time"
}
```

This result is stored on the `Round` record (as JSON in a new `evaluation` JSONB column) and returned in the `submit_answer` response when `round_complete=true`.

#### `react_to_rewrite` — new method

Called when frontend sends a behavioral signal.

```python
async def react_to_rewrite(self, company: str, role: str, rewrite_count: int) -> str
```

Returns a 1-sentence spoken reaction (e.g. "Take your time, there's no rush." or "I notice you're reconsidering — that's fine, just walk me through your thinking."). Uses `deepseek-chat` (fast model).

### `InterviewEngine.submit_answer` — upgraded

New parameters: `time_taken_seconds: int | None`, `rewrite_count: int = 0`.

New logic:
1. Derive `time_elapsed = (utcnow - round.started_at).total_seconds()`
2. Check `time_elapsed >= round.time_budget_seconds` → if so, force `is_last = True` regardless of answer count
3. Pass `time_taken_seconds` and `rewrite_count` to `grade_answer`
4. Store `is_followup`, `time_taken_seconds`, `rewrite_count` on the new `RoundMoment` columns
5. If `round_complete`, call `evaluate_candidate` with all moments for that round
6. The `follow_up` field from `grade_answer` is passed back to the frontend only if `time_elapsed < 0.8 * round.time_budget_seconds`; otherwise it is suppressed

Return schema gains:
```json
{
  "follow_up": "string | null",
  "evaluation": { ... },  // only present when round_complete=true
  "time_remaining_seconds": 1240,
  "confidence_signal": "confident | hesitant | uncertain | rushed"
}
```

### New endpoint: `POST /interview-sessions/{id}/behavioral-signal`

Request:
```json
{ "signal": "rewrite", "rewrite_count": 2 }
```

Response:
```json
{ "reaction": "Take your time, there's no rush." }
```

This endpoint calls `LLMOrchestrator.react_to_rewrite()` and returns immediately. Fire-and-forget from the frontend — no awaiting required for UX.

### `AnswerRequest` schema — new fields

```python
class AnswerRequest(BaseModel):
    round_id: str
    question: str
    answer: str
    total_questions: int = 5
    emotion_state: Optional[str] = None
    time_taken_seconds: Optional[int] = None
    rewrite_count: int = 0
    is_followup: bool = False
```

---

## Section 3: Frontend Changes

### `InterviewSession.tsx`

#### Timer tracking

```typescript
const questionStartTimeRef = useRef<number>(Date.now())

// Reset on every new question (including follow-ups)
useEffect(() => {
  questionStartTimeRef.current = Date.now()
}, [question])

// On submit:
const timeTakenSeconds = Math.floor((Date.now() - questionStartTimeRef.current) / 1000)
```

#### Rewrite detection

```typescript
const prevAnswerLengthRef = useRef(0)
const rewriteCountRef = useRef(0)

const handleAnswerChange = (newValue: string) => {
  const dropped = prevAnswerLengthRef.current - newValue.length
  if (dropped >= 40) {
    rewriteCountRef.current += 1
    // Fire behavioral signal (non-blocking)
    apiFetch(`${API}/interview-sessions/${sessionId}/behavioral-signal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signal: 'rewrite', rewrite_count: rewriteCountRef.current }),
    }).then(r => r.json()).then(j => {
      if (j.data?.reaction) setAvatarReaction(j.data.reaction)
    }).catch(() => {})
  }
  prevAnswerLengthRef.current = newValue.length
  setAnswer(newValue)
}
```

#### Avatar reaction for rewrites

New state `avatarReaction: string | null` — displayed in the avatar panel, auto-cleared after 8 seconds. Same pattern as existing `codeReaction`.

#### Follow-up injection

New state: `followUpQuestion: string | null` and `isFollowUp: boolean`.

After receiving `result.follow_up` from a graded answer:
- If not null: set `followUpQuestion = result.follow_up`, `isFollowUp = true`
- On "Next →" click: if `followUpQuestion` is set, display it as the current question with a "↩ Follow-up" label; do NOT call `nextQuestion()` on the store
- After the follow-up is submitted: clear `followUpQuestion`, `isFollowUp`, then call `nextQuestion()` as normal

Follow-up answers are submitted with `is_followup: true` in the `AnswerRequest`.

#### Time warning banner

Session start response includes `time_budget_seconds` per round. Track `roundStartTime = Date.now()` on round creation. A `useEffect` polling every 30 seconds checks elapsed time:
- `> 80%`: amber banner "Interview ending soon"
- `> 95%`: red banner "Time almost up — submitting your current answer shortly"
- `= 100%`: auto-submit if answer is non-empty, or skip if empty

#### Submit payload

```typescript
await submitAnswer(sessionId, roundId, question, answer, {
  totalQuestions,
  emotionState: undefined,
  timeTakenSeconds,
  rewriteCount: rewriteCountRef.current,
  isFollowup: isFollowUp,
})
```

### `useInterviewSession.ts`

`submitAnswer` passes `time_taken_seconds`, `rewrite_count`, `is_followup` in the POST body.

### `interviewStore.ts`

`setSession` and session start response carries `time_budget_seconds` for the current round.

---

## Section 4: LLM Prompt Design

### Grading prompt (brutal honesty)

```
You are a senior interviewer at {company} evaluating a {role} candidate.

You are direct, fair, and brutally honest. You do not inflate scores to be encouraging.
Scoring guide:
- 9-10: Exceptional. Would hire immediately.
- 7-8: Good. Meets bar for this role.
- 5-6: Mediocre. Passes but has gaps.
- 3-4: Poor. Significant gaps or errors.
- 1-2: Unacceptable. Wrong facts, no structure, or completely off-topic.

Factual accuracy: If the candidate states something demonstrably false (e.g. incorrect technical claims, impossible scenarios), note it explicitly and lower the score accordingly.

Behavioral context:
{timing_note}
{rewrite_note}

Question: {question}
Candidate answer: {answer}

Return JSON only:
{"score": 6.5, "passed": true, "what_worked": "...", "what_was_missing": "...", "stronger_version": "...", "follow_up": "...", "factual_errors": [], "confidence_signal": "..."}
```

### Holistic evaluation prompt

```
You are the hiring manager at {company}. A candidate just completed a {round_type} interview for {role}.

Full transcript with behavioral data:
{transcript_with_timing}

Time used: {actual_duration_seconds}s of {time_budget_seconds}s allowed.

Evaluate the candidate holistically. Consider:
- The quality and depth of their answers across all questions
- Follow-up performance (did they recover from weak initial answers?)
- Consistency — were they strong early and weak later, or the reverse?
- Confidence signals — response times, rewrites, hesitation patterns
- Factual accuracy across the session
- Whether you got enough signal to make a hire decision

Be honest and direct. Do not hedge.

Return JSON only:
{"hire_recommendation": "...", "confidence_rating": "...", "overall_score": 7.2, "summary": "...", "strengths": [...], "concerns": [...], "time_management": "..."}
```

---

## Error Handling

- `react_to_rewrite` failure → silent, no UI impact (fire-and-forget)
- `evaluate_candidate` failure → fall back to average of moment scores, `hire_recommendation = "borderline"`, log error
- Time budget enforcement is backend-only — frontend auto-submit is best-effort; backend enforces `time_elapsed >= budget → force last`
- Follow-up suppressed server-side when time > 80% — client doesn't need to know the threshold

---

## Testing

- Unit tests for `grade_answer` with timing/rewrite params: verify confidence_signal and follow_up fields
- Unit test for `evaluate_candidate`: mock moments, verify hire_recommendation in valid enum
- Unit test for timing classification thresholds (< 10s, 10–120s, 120–180s, > 180s)
- Unit test for time budget enforcement in `submit_answer`: mock `round.started_at` to be near-expired
- Frontend: TypeScript check passes; rewrite detection logic tested with simulated textarea events

---

## Files Changed

### Backend
- `backend/app/models/pg/session.py` — add 5 new columns
- `backend/migrations/versions/<hash>_add_behavioral_signal_columns.py` — new migration
- `backend/app/services/llm_orchestrator.py` — upgrade `grade_answer`, add `evaluate_candidate`, add `react_to_rewrite`
- `backend/app/services/interview_engine.py` — upgrade `submit_answer`, add time budget logic, call `evaluate_candidate`
- `backend/app/schemas/session.py` — upgrade `AnswerRequest`, add `BehavioralSignalRequest`
- `backend/app/api/v1/sessions.py` — add behavioral signal endpoint

### Frontend
- `frontend/src/components/interview/InterviewSession.tsx` — timer, rewrite detection, follow-up flow, time banner
- `frontend/src/hooks/useInterviewSession.ts` — pass new fields in submit
- `frontend/src/store/interviewStore.ts` — carry `time_budget_seconds`
