from typing import Optional
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round_types: list[str]
    career_track: str = "technology"
    level: str = "mid_level"
    interview_stage: str = "hr_interview"
    jd_text: str | None = None
    manager_name: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    round_id: str
    company: str
    role: str
    current_round: str
    remaining_rounds: list[str]
    questions: list[str]
    persona: str


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
