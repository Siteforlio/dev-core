from typing import Optional
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round_types: list[str]


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


class GradeResponse(BaseModel):
    score: float
    passed: bool
    feedback: str
    next_round: Optional[str] = None
    session_complete: bool = False
