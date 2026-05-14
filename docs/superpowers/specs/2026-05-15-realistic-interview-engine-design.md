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
| `started_at` | `DateTime`, default utcnow | Set by SQLAlchemy column default when the round row is created — no call-site change needed in `create_session` or `advance_to_next_round` |
| `time_budget_seconds` | `Integer`, nullable | Max allowed seconds for this round type — set explicitly when creating `Round` |
| `evaluation` | `JSONB`, nullable | Holistic evaluation result stored when round closes |

**Total new columns: 6** (3 on `RoundMoment`, 3 on `Round`).

Note: `started_at` on `Round` is distinct from the existing `started_at` on `InterviewSession` — they are different tables with no ORM conflict.

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

`time_budget_seconds` is looked up from this dict when creating a `Round` and stored on the row:
```python
budget = ROUND_TIME_BUDGETS.get(round_type, DEFAULT_TIME_BUDGET)
round_ = Round(id=..., session_id=..., type=round_type, time_budget_seconds=budget)
```

This applies in both `create_session` and `advance_to_next_round`.

### Alembic migration

One migration: `add_behavioral_signal_columns` — adds all **six** new columns across two tables.

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

Return schema:
```json
{
  "score": 6.5,
  "what_worked": "One clear sentence.",
  "what_was_missing": "One clear sentence.",
  "stronger_version": "One sentence showing improvement.",
  "follow_up": "Follow-up question string if score < 7 and there is a specific gap worth probing, else null",
  "factual_errors": ["List of factual errors found, empty if none"],
  "confidence_signal": "confident | hesitant | uncertain | rushed"
}
```

**Note: `passed` is removed from the LLM return schema.** The engine derives `passed` from `score >= PASS_THRESHOLD` to avoid the dual-check inconsistency. `PASS_THRESHOLD` changes from 6.0 to 5.0.

Pass threshold: `PASS_THRESHOLD = 5.0` (down from 6.0 — follow-ups compensate for initial weak answers).
Fail threshold: `FAIL_THRESHOLD = 3.0` (unchanged — immediate round fail).

The engine sets `grade["passed"] = grade["score"] >= PASS_THRESHOLD` after receiving the LLM result.

#### `evaluate_candidate` — new method

Called once when a round closes (last prepared question answered or time budget expired). Receives the full round transcript including follow-ups, timing data per moment, and rewrite counts.

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

This result is stored in the `Round.evaluation` JSONB column and returned in the `submit_answer` response when `round_complete=true`.

#### `react_to_rewrite` — new method

```python
async def react_to_rewrite(self, company: str, role: str, rewrite_count: int) -> str
```

Returns a 1-sentence spoken reaction. Uses `deepseek-chat` (fast model).

### `InterviewEngine.submit_answer` — upgraded

New signature:
```python
async def submit_answer(
    self,
    session_id: str,
    round_id: str,
    question: str,
    answer: str,
    total_questions: int = 5,
    emotion_state: str | None = None,
    time_taken_seconds: int | None = None,
    rewrite_count: int = 0,
    is_followup: bool = False,
) -> dict
```

New logic (in order):

1. Look up `round_` and `session` as before
2. Derive `time_elapsed = (_utcnow() - round_.started_at).total_seconds()` — use `_utcnow()` (the module-local naive helper) to match the stored naive datetime and avoid timezone arithmetic errors
3. Check `time_elapsed >= round_.time_budget_seconds` → if so, force `is_last = True`
4. **Follow-up counting**: the `is_last` check uses only **non-followup** answers:
   ```python
   count_result = await self.db.execute(
       select(func.count()).select_from(RoundMoment).where(
           RoundMoment.round_id == round_id,
           RoundMoment.is_followup == False,  # noqa: E712
       )
   )
   prepared_count = count_result.scalar()
   is_last = is_last or (prepared_count >= total_questions)
   ```
   Follow-up moments are stored and graded but do not count toward the 5-question completion check.
5. Pass `time_taken_seconds` and `rewrite_count` to `grade_answer`
6. Engine sets `grade["passed"] = grade["score"] >= PASS_THRESHOLD`
7. Store `RoundMoment` with new columns: `time_taken_seconds`, `rewrite_count`, `is_followup`
8. If `round_complete`: fetch all moments for the round, call `evaluate_candidate`, store result in `round_.evaluation`
9. Suppress `follow_up` in response if `time_elapsed >= 0.8 * round_.time_budget_seconds`

Full return schema:
```json
{
  "score": 7.0,
  "passed": true,
  "what_worked": "...",
  "what_was_missing": "...",
  "stronger_version": "...",
  "follow_up": "string | null",
  "confidence_signal": "confident | hesitant | uncertain | rushed",
  "factual_errors": [],
  "round_complete": false,
  "round_passed": null,
  "evaluation": null,
  "time_remaining_seconds": 1240
}
```

`evaluation` is populated only when `round_complete=true`. `time_remaining_seconds = max(0, round_.time_budget_seconds - time_elapsed)`.

### `InterviewEngine.create_session` and `advance_to_next_round` — updated

Both must pass `time_budget_seconds` when creating `Round`:
```python
budget = ROUND_TIME_BUDGETS.get(round_type, DEFAULT_TIME_BUDGET)
round_ = Round(id=str(uuid.uuid4()), session_id=session.id, type=round_type, time_budget_seconds=budget)
```

Both return `time_budget_seconds` in their response dict:
```python
return {
    ...existing fields...,
    "time_budget_seconds": budget,
}
```

### New endpoint: `POST /interview-sessions/{id}/behavioral-signal`

```python
@router.post("/{session_id}/behavioral-signal")
async def behavioral_signal(
    session_id: str,
    body: BehavioralSignalRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Look up session to get company and role
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        return {"data": {"reaction": ""}, "error": None}
    orchestrator = LLMOrchestrator()
    reaction = await orchestrator.react_to_rewrite(
        company=session.company, role=session.role, rewrite_count=body.rewrite_count
    )
    return {"data": {"reaction": reaction}, "error": None}
```

Auth: `Depends(get_user_id)` is required (same as all other session endpoints).

### Updated `sessions.py` router call for `submit_answer`

```python
result = await engine.submit_answer(
    session_id=session_id,
    round_id=body.round_id,
    question=body.question,
    answer=body.answer,
    total_questions=body.total_questions,
    emotion_state=body.emotion_state,
    time_taken_seconds=body.time_taken_seconds,
    rewrite_count=body.rewrite_count,
    is_followup=body.is_followup,
)
```

### Schema changes

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

class BehavioralSignalRequest(BaseModel):
    signal: str  # "rewrite"
    rewrite_count: int = 1
```

---

## Section 3: Frontend Changes

### `interviewStore.ts`

The `Round` interface gains:
```typescript
interface Round {
  id: string
  type: string
  questions: string[]
  currentQuestionIndex: number
  passed?: boolean
  feedbackResult?: FeedbackResult
  timeBudgetSeconds: number  // NEW — carried from session start / advance response
}
```

`setSession` accepts `timeBudgetSeconds` and stores it on the round object. `advanceRound` similarly carries `timeBudgetSeconds` from the advance response.

### `useInterviewSession.ts`

`startSession` maps `data.time_budget_seconds` into the round object passed to `setSession`.

`submitAnswer` extended options:
```typescript
opts?: {
  totalQuestions?: number
  emotionState?: string
  timeTakenSeconds?: number
  rewriteCount?: number
  isFollowup?: boolean
}
```

POST body includes `time_taken_seconds`, `rewrite_count`, `is_followup`.

### `InterviewSession.tsx`

#### Timer tracking

```typescript
const questionStartTimeRef = useRef<number>(Date.now())

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
    apiFetch(`/api/v1/interview-sessions/${sessionId}/behavioral-signal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ signal: 'rewrite', rewrite_count: rewriteCountRef.current }),
    }).then(r => r.json()).then(j => {
      if (j.data?.reaction) {
        setAvatarReaction(j.data.reaction)
        setTimeout(() => setAvatarReaction(null), 8000)
      }
    }).catch(() => {})
  }
  prevAnswerLengthRef.current = newValue.length
  setAnswer(newValue)
}
```

Reset `prevAnswerLengthRef.current = 0` and `rewriteCountRef.current = 0` after each submit.

#### Avatar reaction for rewrites

New state `avatarReaction: string | null`. Displayed in the avatar panel alongside `isSpeaking`. Auto-cleared after 8 seconds (set in the `.then` above).

#### Follow-up injection

New component state:
```typescript
const [followUpQuestion, setFollowUpQuestion] = useState<string | null>(null)
const [isFollowUp, setIsFollowUp] = useState(false)
```

After receiving graded result:
- If `result.follow_up` is not null/empty: `setFollowUpQuestion(result.follow_up)`, `setIsFollowUp(true)`
- Display logic: `const question = followUpQuestion ?? currentRound.questions[currentRound.currentQuestionIndex]`
- Label: show `"↩ Follow-up"` badge above question box when `isFollowUp === true`

On "Next →" click:
```typescript
if (followUpQuestion) {
  // Follow-up was just answered — clear it and advance prepared index
  setFollowUpQuestion(null)
  setIsFollowUp(false)
  nextQuestion()  // advance prepared question index as normal
} else if (!roundComplete) {
  nextQuestion()
} else {
  // round over — existing logic
}
```

Follow-up answers submitted with `isFollowup: true` and same `total_questions` as the prepared round (backend ignores follow-ups in its count check).

#### Time warning banner

Derive from store:
```typescript
const timeBudgetSeconds = currentRound?.timeBudgetSeconds ?? 1800
```

Track round start time in a ref:
```typescript
const roundStartTimeRef = useRef<number>(Date.now())
// Reset when round changes (round id changes):
useEffect(() => { roundStartTimeRef.current = Date.now() }, [currentRound?.id])
```

Poll every 30s:
```typescript
useEffect(() => {
  const interval = setInterval(() => {
    const elapsed = (Date.now() - roundStartTimeRef.current) / 1000
    const pct = elapsed / timeBudgetSeconds
    if (pct >= 1.0 && answer.trim()) handleSubmit()
    else if (pct >= 0.95) setTimeWarning('red')
    else if (pct >= 0.80) setTimeWarning('amber')
    else setTimeWarning(null)
  }, 30_000)
  return () => clearInterval(interval)
}, [timeBudgetSeconds, answer])
```

Banner renders above the question box when `timeWarning` is not null.

---

## Section 4: LLM Prompt Design

### Grading prompt (brutal honesty)

```
You are a senior interviewer at {company} evaluating a {role} candidate in a {round_type} interview.

You are direct, fair, and brutally honest. You do not inflate scores to be encouraging.
Scoring guide:
- 9-10: Exceptional. Would hire immediately.
- 7-8: Good. Meets bar for this role.
- 5-6: Mediocre. Passes but has clear gaps.
- 3-4: Poor. Significant gaps, weak structure, or factual errors.
- 1-2: Unacceptable. Wrong facts, no structure, or completely off-topic.

Factual accuracy: If the candidate states something demonstrably false, note it explicitly and lower the score.

Behavioral context:
{timing_note}
{rewrite_note}

Question: {question}
Candidate answer: {answer}

Return JSON only — no other text:
{"score": 6.5, "what_worked": "...", "what_was_missing": "...", "stronger_version": "...", "follow_up": null, "factual_errors": [], "confidence_signal": "confident"}
```

Note: `passed` is NOT in the LLM response — the engine derives it from `score >= PASS_THRESHOLD`.
`follow_up` should be `null` (not the string "null") when no follow-up is warranted.

### Holistic evaluation prompt

```
You are the hiring manager at {company}. A candidate just completed a {round_type} interview for {role}.

Full transcript with behavioral data:
{transcript_with_timing}

Time used: {actual_duration}s of {budget}s allowed.

Evaluate holistically. Consider:
- Answer quality and depth across all prepared questions
- Follow-up performance (did they recover from weak initial answers?)
- Consistency across the session
- Confidence signals: response times, rewrites, hesitation
- Factual accuracy
- Whether you have enough signal to make a hire decision

Be honest and direct. Do not hedge. A "borderline" means you genuinely cannot decide.

Return JSON only:
{"hire_recommendation": "yes", "confidence_rating": "medium", "overall_score": 6.8, "summary": "Two sentences.", "strengths": [...], "concerns": [...], "time_management": "adequate"}
```

---

## Error Handling

- `react_to_rewrite` failure → silent (fire-and-forget, `catch(() => {})` in frontend)
- `evaluate_candidate` failure → fall back to average score of moments, `hire_recommendation = "borderline"`, store fallback in `round_.evaluation`, log error
- `round_.started_at` is always set by column default — if somehow null, skip time budget enforcement (treat as no budget)
- Time budget enforcement is backend-authoritative — frontend auto-submit is best-effort
- Follow-ups suppressed server-side when time > 80% — client does not need to know the threshold

---

## Testing

- Unit test `grade_answer` with `time_taken_seconds < 10`: verify `confidence_signal == "rushed"`
- Unit test `grade_answer` with `time_taken_seconds > 180`: verify timing note in prompt, `confidence_signal` is not "confident"
- Unit test `grade_answer` with `rewrite_count = 3`: verify rewrite note in prompt
- Unit test `grade_answer` does NOT return `passed` field — engine derives it
- Unit test `evaluate_candidate`: mock moments, verify `hire_recommendation` in valid enum
- Unit test `submit_answer` follow-up counting: 3 prepared + 2 follow-up moments → `prepared_count = 3`, not 5 → round not complete
- Unit test time budget enforcement: mock `round_.started_at` 30 minutes ago with 1800s budget → `is_last = True`
- Unit test `react_to_rewrite`: mock session lookup, verify reaction string returned
- Frontend: `npx tsc --noEmit` passes; rewrite detection threshold (≥40 chars dropped) verified with unit test

---

## Files Changed

### Backend
- `backend/app/models/pg/session.py` — add 6 new columns (`RoundMoment`: 3, `Round`: 3)
- `backend/migrations/versions/<hash>_add_behavioral_signal_columns.py` — new migration (6 columns)
- `backend/app/services/llm_orchestrator.py` — upgrade `grade_answer` (remove `passed`, add behavioral params), add `evaluate_candidate`, add `react_to_rewrite`
- `backend/app/services/interview_engine.py` — upgrade `submit_answer` (new params, follow-up count logic, time budget, `evaluate_candidate` call), upgrade `create_session` and `advance_to_next_round` (set `time_budget_seconds` on round, return it)
- `backend/app/schemas/session.py` — upgrade `AnswerRequest`, add `BehavioralSignalRequest`
- `backend/app/api/v1/sessions.py` — add behavioral signal endpoint (with auth), pass new fields through `submit_answer` router call

### Frontend
- `frontend/src/store/interviewStore.ts` — add `timeBudgetSeconds` to `Round` interface, carry through `setSession` and `advanceRound`
- `frontend/src/hooks/useInterviewSession.ts` — map `time_budget_seconds` from response; pass `timeTakenSeconds`, `rewriteCount`, `isFollowup` in submit
- `frontend/src/components/interview/InterviewSession.tsx` — timer tracking, rewrite detection, avatar reaction, follow-up injection, time warning banner, reset refs on submit
