from typing import Optional, Literal
from pydantic import BaseModel, field_validator


# ── JSONB field schemas ───────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    """Shape of Round.evaluation JSONB — produced by llm_orchestrator.evaluate_candidate."""
    hire_recommendation: Literal["strong_yes", "yes", "borderline", "no", "strong_no"] = "borderline"
    confidence_rating: Literal["high", "medium", "low", "erratic"] = "low"
    overall_score: float = 5.0
    summary: str = ""
    strengths: list[str] = []
    concerns: list[str] = []
    time_management: Literal["efficient", "adequate", "slow", "over_time"] = "adequate"

    @field_validator("overall_score", mode="before")
    @classmethod
    def clamp_score(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 5.0
        return max(0.0, min(10.0, v))

    @field_validator("strengths", "concerns", mode="before")
    @classmethod
    def coerce_list(cls, v):
        if isinstance(v, list):
            return [str(i) for i in v]
        return []


class CheatSignal(BaseModel):
    """One entry in Round.cheating_signals JSONB list."""
    type: str
    ts: str
    paste_chars: Optional[int] = None
    duration_seconds: Optional[float] = None
    chars_per_second: Optional[float] = None


class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round_types: list[str]
    career_track: str = "technology"
    level: str = "mid_level"
    interview_stage: str = "hr_interview"
    jd_text: str | None = None
    manager_name: str | None = None


class SkillsTaskSchema(BaseModel):
    title: str
    brief: str
    input_type: str  # "code" | "text"
    language: Optional[str] = None
    starter_code: Optional[str] = None
    evaluation_criteria: list[str] = []
    time_hint: str = "60 minutes"


class SessionResponse(BaseModel):
    session_id: str
    round_id: str
    company: str
    role: str
    current_round: str
    remaining_rounds: list[str]
    questions: list[str]
    task: Optional[SkillsTaskSchema] = None
    persona: str
    time_budget_seconds: Optional[int] = None


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
    rewrite_count: int = 1


class CheatSignalRequest(BaseModel):
    round_id: str
    signal_type: str          # "paste" | "focus_lost" | "velocity_spike" | "tab_switch"
    paste_chars: Optional[int] = None
    duration_seconds: Optional[float] = None
    chars_per_second: Optional[float] = None


class AdvanceRoundRequest(BaseModel):
    next_round_type: str


class GradeResponse(BaseModel):
    score: float
    passed: bool
    what_worked: str
    what_was_missing: str
    stronger_version: str
    next_round: Optional[str] = None
    session_complete: bool = False
